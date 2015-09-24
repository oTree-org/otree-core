#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import urllib
import urlparse
import csv
import datetime
import operator
import contextlib
import inspect
from os.path import dirname, join
from collections import OrderedDict
from importlib import import_module

from django.db import transaction
from django.db import connection
from django.apps import apps
from django.conf import settings
from django.template.defaultfilters import title

import six

from otree import constants_internal


def add_params_to_url(url, params):
    url_parts = list(urlparse.urlparse(url))

    # use OrderedDict because sometimes we want certain params at end
    # for readability/consistency
    query = OrderedDict(urlparse.parse_qsl(url_parts[4]))
    query.update(params)
    url_parts[4] = urllib.urlencode(query)
    return urlparse.urlunparse(url_parts)


def id_label_name(id, label):
    if label:
        return '{} (label: {})'.format(id, label)
    return '{}'.format(id)


def is_subsession_app(app_name):
    try:
        models_module = import_module('{}.models'.format(app_name))
    except ImportError:
        return False
    class_names = ['Player', 'Group', 'Subsession']
    return all(hasattr(models_module, ClassName) for ClassName in class_names)


def git_commit_timestamp():
    root_dir = dirname(settings.BASE_DIR)
    try:
        with open(join(root_dir, 'git_commit_timestamp'), 'r') as f:
            return f.read().strip()
    except IOError:
        return ''


def app_name_format(app_name):
    app_label = app_name.split('.')[-1]
    return title(app_label.replace("_", " "))


def url(cls, session_user, index=None):
    u = '/{}/{}/{}/{}/'.format(
        session_user.user_type_in_url,
        session_user.code,
        cls.get_name_in_url(),
        cls.__name__,
    )

    if index is not None:
        u += '{}/'.format(index)
    return u


def url_pattern(cls, is_sequence_url=False):
    p = r'(?P<{}>\w)/(?P<{}>[a-z]+)/{}/{}/'.format(
        constants_internal.user_type,
        constants_internal.session_user_code,
        cls.get_name_in_url(),
        cls.__name__,
    )
    if is_sequence_url:
        p += r'(?P<{}>\d+)/'.format(constants_internal.index_in_pages,)
    p = r'^{}$'.format(p)
    return p


def directory_name(path):
    return os.path.basename(os.path.normpath(path))


def get_models_module(app_name):
    module_name = '{}.models'.format(app_name)
    return import_module(module_name)


def get_views_module(app_name):
    module_name = '{}.views'.format(app_name)
    return import_module(module_name)


def get_app_constants(app_name):
    '''Return the ``Constants`` object of a app defined in the models.py file.

    Example::

        >>> from otree.subsessions import get_app_constants
        >>> get_app_constants('demo_game')
        <class demo_game.models.Constants at 0x7fed46bdb188>

    '''
    return get_models_module(app_name).Constants


def export_data(fp, app_name):
    """Write the data of the given app name as csv into the file-like object

    """
    from otree.views.admin import get_display_table_rows
    colnames, rows = get_display_table_rows(
        app_name, for_export=True, subsession_pk=None)
    colnames = ['{}.{}'.format(k, v) for k, v in colnames]
    writer = csv.writer(fp)
    writer.writerows([colnames])
    writer.writerows(rows)


def export_time_spent(fp):
    """Write the data of the timespent on each_page as csv into the file-like
    object

    """
    from otree.models_concrete import PageCompletion
    from otree.views.admin import get_all_fields

    columns = get_all_fields(PageCompletion)
    rows = PageCompletion.objects.order_by(
        'session_pk', 'participant_pk', 'page_index').values_list(*columns)
    writer = csv.writer(fp)
    writer.writerows([columns])
    writer.writerows(rows)


def export_docs(fp, app_name):
    """Write the dcos of the given app name as csv into the file-like object

    """
    from otree.models import session
    from otree.views.admin import get_all_fields

    # generate doct_dict
    models_module = get_models_module(app_name)

    model_names = ["Participant", "Player", "Group", "Subsession", "Session"]
    line_break = '\r\n'

    def choices_readable(choices):
        lines = []
        for value, name in choices:
            # unicode() call is for lazy translation strings
            lines.append(u'{}: {}'.format(value, unicode(name)))
        return lines

    def generate_doc_dict():
        doc_dict = OrderedDict()

        data_types_readable = {
            'PositiveIntegerField': 'positive integer',
            'IntegerField': 'integer',
            'BooleanField': 'boolean',
            'CharField': 'text',
            'TextField': 'text',
            'FloatField': 'decimal',
            'DecimalField': 'decimal',
            'CurrencyField': 'currency'}

        for model_name in model_names:
            if model_name == 'Participant':
                Model = session.Participant
            elif model_name == 'Session':
                Model = session.Session
            else:
                Model = getattr(models_module, model_name)

            field_names = set(field.name for field in Model._meta.fields)

            members = get_all_fields(Model, for_export=True)
            doc_dict[model_name] = OrderedDict()

            for member_name in members:
                member = getattr(Model, member_name, None)
                doc_dict[model_name][member_name] = OrderedDict()
                if member_name == 'id':
                    doc_dict[model_name][member_name]['type'] = [
                        'positive integer']
                    doc_dict[model_name][member_name]['doc'] = ['Unique ID']
                elif member_name in field_names:
                    member = Model._meta.get_field_by_name(member_name)[0]

                    internal_type = member.get_internal_type()
                    data_type = data_types_readable.get(
                        internal_type, internal_type)

                    doc_dict[model_name][member_name]['type'] = [data_type]

                    # flag error if the model doesn't have a doc attribute,
                    # which it should unless the field is a 3rd party field
                    doc = getattr(member, 'doc', '[error]') or ''
                    doc_dict[model_name][member_name]['doc'] = [
                        line.strip() for line in doc.splitlines()
                        if line.strip()]

                    choices = getattr(member, 'choices', None)
                    if choices:
                        doc_dict[model_name][member_name]['choices'] = (
                            choices_readable(choices))
                elif callable(member):
                    doc_dict[model_name][member_name]['doc'] = [
                        inspect.getdoc(member)]
        return doc_dict

    def docs_as_string(doc_dict):

        first_line = '{}: Documentation'.format(app_name_format(app_name))
        second_line = '*' * len(first_line)

        lines = [
            first_line, second_line, '',
            'Accessed: {}'.format(datetime.date.today().isoformat()), '']

        app_doc = getattr(models_module, 'doc', '')
        if app_doc:
            lines += [app_doc, '']

        for model_name in doc_dict:
            lines.append(model_name)

            for member in doc_dict[model_name]:
                lines.append('\t{}'.format(member))
                for info_type in doc_dict[model_name][member]:
                    lines.append('\t\t{}'.format(info_type))
                    for info_line in doc_dict[model_name][member][info_type]:
                        lines.append(u'{}{}'.format('\t' * 3, info_line))

        output = u'\n'.join(lines)
        return output.replace('\n', line_break).replace('\t', '    ')

    doc_dict = generate_doc_dict()
    doc = docs_as_string(doc_dict)
    fp.write(doc)


def flatten(list_of_lists):
    return [item for sublist in list_of_lists for item in sublist]


def get_app_label_from_import_path(import_path):
    app_label = import_path.rsplit(".", 1)[0]
    while "." in app_label:
        app_label = app_label.rsplit(".", 1)[-1]
    return app_label


def get_app_name_from_label(app_label):
    '''
    >>> get_app_name_from_label('simple_game')
    'tests.simple_game'

    '''
    return apps.get_app_config(app_label).name


def get_players(self, order_by, refresh_from_db=False):
    if refresh_from_db or not self._players:
        self._players = list(self.player_set.all())
    return sorted(self._players, key=operator.attrgetter(order_by))


def get_groups(self, refresh_from_db=False):
    if refresh_from_db or not self._groups:
        self._groups = self.group_set.all()
    return list(self._groups)


def expand_choice_tuples(choices):
    '''allows the programmer to define choices as a list of values rather
    than (value, display_value)

    '''
    if not choices:
        return None
    elif not isinstance(choices[0], (list, tuple)):
        choices = [(value, value) for value in choices]
    return choices


def contract_choice_tuples(choices):
    '''Return only values of a choice tuple. If the choices are simple lists
    without display name the same list is returned

    '''
    if not choices:
        return None
    elif not isinstance(choices[0], (list, tuple)):
        return choices
    return [value for value, _ in choices]


def min_players_multiple(players_per_group):
    ppg = players_per_group

    if isinstance(ppg, (int, long)) and ppg >= 1:
        return ppg
    if isinstance(ppg, (list, tuple)):
        return sum(ppg)
    # else, it's probably None
    return 1


def reraise(original):
    """Convert an exception in another type specified by
    ``constants.exception_conversors``

    """
    original_cls = type(original)
    if original_cls in constants_internal.exceptions_conversors:
        conversor = constants_internal.exceptions_conversors[original_cls]
        new = conversor(original)
        new_cls = type(new)
        six.reraise(new_cls, new, sys.exc_traceback)
    else:
        six.reraise(original_cls, original, sys.exc_traceback)


def db_table_exists(table_name):
    """Return True if a table already exists"""
    return table_name in connection.introspection.table_names()


def db_status_ok():
    """Try to execute a simple select * for every model registered

    """
    for Model in apps.get_models():
        table_name = Model._meta.db_table
        if not db_table_exists(table_name):
            return False
    return True


@contextlib.contextmanager
def no_op_context_manager():
    yield


@contextlib.contextmanager
def transaction_atomic():
    if settings.DATABASES['default']['ENGINE'].endswith('sqlite3'):
        yield
    else:
        with transaction.atomic():
            yield


@contextlib.contextmanager
def lock_on_this_code_path():
    with transaction_atomic():
        # take a lock on this singleton, so that only 1 person can
        # be completing this code path at once
        from otree.models.session import GlobalSingleton
        GlobalSingleton.objects.select_for_update().get()
        yield
