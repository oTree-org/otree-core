import binascii
import logging
import os
import pickle
import sqlite3
import sys
from contextlib import contextmanager
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from typing import List

import sqlalchemy
import sqlalchemy.orm
import sqlalchemy.pool
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import create_engine
from sqlalchemy import types
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.mutable import Mutable
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound  # noqa
from sqlalchemy.sql import sqltypes as st
from starlette.exceptions import HTTPException

from otree import __version__
from otree.common import expand_choice_tuples
from otree.currency import Currency, RealWorldCurrency

logger = logging.getLogger(__name__)
DB_FILE = 'db.sqlite3'


# DB_FILE_PATH = Path(DB_FILE)


def get_disk_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)


def get_mem_conn():
    return sqlite3.connect(':memory:', check_same_thread=False)


def get_schema(conn):
    conn.text_factory = str
    cur = conn.cursor()

    result = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table';"
    ).fetchall()
    table_names = sorted(list(zip(*result))[0])

    d = {}
    for table_name in table_names:
        result = cur.execute("PRAGMA table_info('%s')" % table_name).fetchall()
        d[table_name] = list(zip(*result))[1]
    return d


NEW_SCOPE_EACH_REQUEST = False

sqlite_mem_conn = get_mem_conn()
sqlite_disk_conn = get_disk_conn()

_dumped = False


class OTreeColumn(sqlalchemy.Column):
    form_props: dict
    auto_submit_default = None


def load_in_memory_db():
    old_schema = get_schema(sqlite_disk_conn)
    new_schema = get_schema(sqlite_mem_conn)

    disk_cur = sqlite_disk_conn.cursor()
    mem_cur = sqlite_mem_conn.cursor()

    prev_version = sqlite_disk_conn.execute("PRAGMA user_version").fetchone()[0]

    # They should start fresh so that:
    # (1) performance refresh
    # (2) don't have to worry about old references to things that were removed from otree-core.
    if prev_version != version_for_pragma():
        sys.exit(f'oTree has been updated. Please delete your database ({DB_FILE})')

    for tblname in new_schema:
        if tblname in old_schema:
            common_cols = [c for c in old_schema[tblname] if c in new_schema[tblname]]
            common_cols_joined = ', '.join(common_cols)
            select_cmd = f'SELECT {common_cols_joined} FROM {tblname}'
            question_marks = ', '.join('?' for _ in common_cols)
            insert_cmd = (
                f'INSERT INTO {tblname}({common_cols_joined}) VALUES ({question_marks})'
            )
            disk_cur.execute(select_cmd)
            rows = disk_cur.fetchall()
            mem_cur.executemany(insert_cmd, rows)
    sqlite_mem_conn.commit()


@contextmanager
def session_scope():
    if not NEW_SCOPE_EACH_REQUEST:
        db.new_session()
    try:
        yield
        db.commit()
    except:
        db.rollback()
        raise
    finally:
        if not NEW_SCOPE_EACH_REQUEST:
            db.close()


def save_sqlite_db(*args):
    global _dumped
    if _dumped:
        return
    sqlite_mem_conn.cursor().execute(f"PRAGMA user_version = {version_for_pragma()}")
    sqlite_mem_conn.backup(sqlite_disk_conn)
    _dumped = True
    sys.stdout.write('Database saved\n')


DeclarativeBase = declarative_base()


class DBWrapper:
    """
    1. this way we can defer definining the ._db attribute
    until all modules are imported
    2. we can add helper methods
    """

    _db: sqlalchemy.orm.Session = None

    def query(self, *args, **kwargs):
        return self._db.query(*args, **kwargs)

    def add(self, obj):
        return self._db.add(obj)

    def add_all(self, objs):
        return self._db.add_all(objs)

    def delete(self, obj):
        return self._db.delete(obj)

    def get_or_404(self, Model, msg='Not found', **kwargs):
        try:
            return self.query(Model).filter_by(**kwargs).one()
        except sqlalchemy.orm.exc.NoResultFound:
            msg = f'{msg}: {Model.__name__}, {kwargs}'
            raise HTTPException(404, msg)

    def commit(self):
        try:
            return self._db.commit()
        except:
            self._db.rollback()
            raise

    def rollback(self):
        return self._db.rollback()

    def close(self):
        return self._db.close()

    def new_session(self):
        if os.getenv('OTREE_EPHEMERAL'):
            self._db = DBSession(bind=ephemeral_connection)
        else:
            self._db = DBSession()

    def expire_all(self):
        self._db.expire_all()


db = DBWrapper()
dbq = db.query

# is_test = 'test' in sys.argv
# # is_devserver = 'devserver_inner' in sys.argv
# # is_devserver = False  ## FIXME: dont use in memory DB for now
# is_devserver = True


IN_MEMORY = bool(os.getenv('OTREE_IN_MEMORY'))


def get_engine():
    if IN_MEMORY:
        engine = create_engine(
            'sqlite://',
            creator=lambda: sqlite_mem_conn,
            # with NullPool i get 'cannot
            poolclass=sqlalchemy.pool.StaticPool,
        )
    else:
        DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{DB_FILE}')
        kwargs = {}
        if DATABASE_URL.startswith('sqlite'):
            kwargs['creator'] = lambda: sqlite_disk_conn
        engine = create_engine(
            DATABASE_URL, poolclass=sqlalchemy.pool.StaticPool, **kwargs,
        )
    return engine


engine = get_engine()

DBSession = sessionmaker(bind=engine)

ephemeral_connection = None


def init_orm():
    from otree.settings import OTREE_APPS

    # import all models so it's loaded into the engine?
    for app in OTREE_APPS:
        try:
            models = import_module(f'{app}.models')
        except Exception as exc:
            # to produce a smaller traceback
            import traceback

            traceback.print_exc()
            sys.exit(1)
        for cls in [models.Player, models.Group, models.Subsession]:
            # TODO:
            # fields = []
            # for name, value in cls.__dict__.items():
            #     if isinstance(value, OTreeColumn):
            #     if hasattr(cls, name + '_choices'):
            #         method_name = f'get_{name}_display'
            #         setattr(cls, method_name, make_get_display(name))
            #
            # cls._setattr_fields = frozenset(f.name for f in new_class._meta.fields)
            # cls._setattr_attributes = frozenset(dir(new_class))
            pass

    import otree.models_concrete  # noqa

    AnyModel.metadata.create_all(engine)

    if (
        IN_MEMORY
        and not os.getenv('OTREE_EPHEMERAL')
        and Path(DB_FILE).exists()
        and Path(DB_FILE).stat().st_size > 0
    ):
        load_in_memory_db()

    db.new_session()


class AnyModel(DeclarativeBase):
    __abstract__ = True

    id = OTreeColumn(st.Integer, primary_key=True)

    def __repr__(self):
        return '<{} id={}>'.format(self.__class__.__name__, self.id)

    @declared_attr
    def __tablename__(cls):
        return cls.get_folder_name() + '_' + cls.__name__.lower()

    @classmethod
    def get_folder_name(cls):
        name = cls.__module__.split('.')[-2]
        return name

    def _clone(self):
        return type(self).objects_get(id=self.id)

    @classmethod
    def objects_get(cls, *args, **kwargs) -> 'AnyModel':
        try:
            return cls.objects_filter(*args, **kwargs).one()
        except Exception as exc:
            raise

    @classmethod
    def objects_first(cls, *args, **kwargs) -> 'AnyModel':
        return cls.objects_filter(*args, **kwargs).first()

    @classmethod
    def objects_filter(cls, *args, **kwargs):
        return dbq(cls).filter(*args).filter_by(**kwargs)

    @classmethod
    def objects_exists(cls, *args, **kwargs) -> bool:
        return bool(cls.objects_filter(*args, **kwargs).first())

    @classmethod
    def values_dicts(cls, *args, order_by=None, **kwargs):
        query = cls.objects_filter(*args, **kwargs)
        if order_by:
            query = query.order_by(order_by)
        names = [f.name for f in cls.__table__.columns]
        fields = [getattr(cls, name) for name in names]
        # i if I use .values(), I get 'no such column: id'
        return [dict(zip(names, row)) for row in query.with_entities(*fields)]

    @classmethod
    def objects_create(cls, **kwargs) -> 'AnyModel':
        obj = cls(**kwargs)
        db.add(obj)
        return obj


class SSPPGModel(AnyModel):
    __abstract__ = True

    _is_frozen = False
    NoneType = type(None)

    _setattr_datatypes = {
        # first value should be the "recommmended" datatype,
        # because that's what we recommend in the error message.
        # it seems the habit of setting boolean values to 0 or 1
        # is very common. that's even what oTree shows in the "live update"
        # view, and the data export.
        'BooleanField': (bool, int, NoneType),
        # forms seem to save Decimal to CurrencyField
        'CurrencyField': (Currency, NoneType, int, float, Decimal),
        'FloatField': (float, NoneType, int),
        'IntegerField': (int, NoneType),
        'StringField': (str, NoneType),
        'LongStringField': (str, NoneType),
    }
    _setattr_whitelist = {
        '_initial_prep_values',
        # used by Prefetch.
        '_ordered_players',
        '_is_frozen',
        # extras on 2018-11-24
        'id',
        '_changed_fields',
        'id',
    }

    '''
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # cache it for performance
        self._super_setattr = super().__setattr__
        # originally I had:
        # self._dir_attributes = set(dir(self))
        # but this tripled memory usage when creating a session
        # we still need some kind of 'save the change' logic because we don't want .update() queries
        # to be overwritten when the player model is saved.
        self._is_frozen = True

    def __setattr__(self, field_name: str, value):
        if self._is_frozen:

            if field_name in self._setattr_fields:
                # hasattr() cannot be used inside
                # a Django model's setattr, as I discovered.
                field = self._meta.get_field(field_name)

                field_type_name = type(field).__name__
                if field_type_name in self._setattr_datatypes:
                    allowed_types = self._setattr_datatypes[field_type_name]
                    if (
                        isinstance(value, allowed_types)
                        # numpy uses its own datatypes, e.g. numpy._bool,
                        # which doesn't inherit from python bool.
                        or 'numpy' in str(type(value))
                        # 2018-07-18:
                        # have an exception for the bug in the 'quiz' sample game
                        # after a while, we can remove this
                        or field_name == 'question_id'
                    ):
                        pass
                    else:
                        msg = ('{} should be set to {}, not {}.').format(
                            field_type_name,
                            allowed_types[0].__name__,
                            type(value).__name__,
                        )
                        raise TypeError(msg)
            elif (
                field_name in self._setattr_attributes
                or field_name in self._setattr_whitelist
                or
                # idmap uses _group_cache, _subsession_cache,
                # _prefetched_objects_cache, etc
                field_name.endswith('_cache')
            ):
                # django sometimes reassigns to non-field attributes that
                # were set before the class was frozen, such as
                # .id and ._changed_fields (from SaveTheChange)
                # or assigning to a property like Player.payoff
                pass
            else:
                msg = ('{} has no field "{}".').format(
                    self.__class__.__name__, field_name
                )
                raise AttributeError(msg)
            if field_name in self._setattr_fields and field_name not in ['id']:
                self._update_fields.add(field_name)
            self._super_setattr(field_name, value)
        else:
            # super() is a bit slower but only gets run during __init__
            super().__setattr__(field_name, value)
    '''


class MixinSessionFK:
    @declared_attr
    def session_id(cls):
        return OTreeColumn(st.Integer, ForeignKey(f'otree_session.id'))

    @declared_attr
    def session(cls):
        return relationship(f'Session')


class VarsError(Exception):
    pass


def values_flat(query, field) -> list:
    return [val for [val] in query.with_entities(field)]


def inspect_obj(obj):
    if isinstance(obj, AnyModel):
        msg = (
            "Cannot store '{}' object in vars. "
            "participant.vars and session.vars "
            "cannot contain model instances, "
            "like Players, Groups, etc.".format(repr(obj))
        )
        raise VarsError(msg)


def scan_for_model_instances(vars_dict: dict):
    '''
    I don't know how to entirely block pickle from storing model instances,
    (I tried overriding __reduce__ but that interferes with deepcopy())
    so this simple shallow scan should be good enough.
    '''

    for v in vars_dict.values():
        inspect_obj(v)
        if isinstance(v, dict):
            for vv in v.values():
                inspect_obj(vv)
        elif isinstance(v, list):
            for ele in v:
                inspect_obj(ele)


def make_get_display(name):
    def get_FIELD_display(self):
        choices = getattr(self, name + '_choices')()
        value = getattr(self, name)
        return dict(expand_choice_tuples(choices))[value]

    return get_FIELD_display


class VarsDict(Mutable, dict):
    @classmethod
    def coerce(cls, key, value):
        if not isinstance(value, VarsDict):
            if isinstance(value, dict):
                return VarsDict(value)

            # this call will raise ValueError
            return Mutable.coerce(key, value)
        else:
            return value


class _PickleField(types.TypeDecorator):
    impl = types.Text

    def process_bind_param(self, value, dialect):
        # for some reason this doesn't print the actual VarsError, but rather
        # a really ugly sqlalchemy.exc.StatementError.
        # scan_for_model_instances(value)
        return binascii.b2a_base64(pickle.dumps(dict(value))).decode('utf-8')

    def process_result_value(self, value, dialect):
        return pickle.loads(binascii.a2b_base64(value.encode('utf-8')))


class MixinVars:
    _vars = Column(VarsDict.as_mutable(_PickleField), default=VarsDict)

    @property
    def vars(self):
        self._vars.changed()
        return self._vars


class BaseCurrencyType(types.TypeDecorator):

    impl = types.Text()

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(Decimal(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self.MONEY_CLASS(Decimal(value))

    MONEY_CLASS = None  # need to set in subclasses


class CurrencyType(BaseCurrencyType):
    MONEY_CLASS = Currency


class RealWorldCurrencyType(BaseCurrencyType):
    MONEY_CLASS = RealWorldCurrency


AUTO_SUBMIT_DEFAULTS = {
    st.Boolean: False,
    st.Integer: 0,
    st.Float: 0,
    st.String: '',
    st.Text: '',
    RealWorldCurrencyType: Currency(0),
    CurrencyType: RealWorldCurrency(0),
}


def wrap_column(coltype, *, initial=None, null=True, **form_props) -> OTreeColumn:
    if 'default' in form_props:
        raise Exception("Don't use default= in model fields. Use initial= instead.")
    col = OTreeColumn(coltype, default=initial, nullable=null)
    col.form_props = form_props

    col.auto_submit_default = AUTO_SUBMIT_DEFAULTS[
        coltype if isinstance(coltype, type) else type(coltype)
    ]
    return col


def BooleanField(**kwargs):
    return wrap_column(st.Boolean, **kwargs)


def StringField(**kwargs):
    return wrap_column(st.String(length=kwargs.get('max_length', 10000)), **kwargs,)


def LongStringField(**kwargs):
    return wrap_column(st.Text, **kwargs)


def FloatField(**kwargs):
    return wrap_column(st.Float, **kwargs)


def IntegerField(**kwargs):
    return wrap_column(st.Integer, **kwargs)


def CurrencyField(**kwargs):
    return wrap_column(CurrencyType, **kwargs)


def RealWorldCurrencyField(**kwargs):
    return wrap_column(RealWorldCurrencyType, **kwargs)


# aliases for compat
CharField = StringField
PositiveIntegerField = IntegerField


def get_changed_columns(old_schema, new_schema):
    return dict(
        dropped_tables=None, new_tables=None, dropped_columns=None, new_columns=None
    )


def version_for_pragma() -> int:
    # e.g. '3.0.25b1' -> 3025
    # not perfect but as long as it works 95% of the time it's good enough
    return int(''.join(c for c in __version__ if c in '0123456789'))
