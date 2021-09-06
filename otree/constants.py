from otree.i18n import core_gettext


class MustCopyError(Exception):
    pass


def _raise_must_copy(*args, **kwargs):
    msg = (
        "Cannot modify a list that originated in your constants class. "
        "First, you must make a copy of it, e.g. mylist.copy() "
        "This is to prevent accidentally modifying the original list. "
    )
    raise MustCopyError(msg)


class ConstantsList(list):

    __setitem__ = _raise_must_copy
    __delitem__ = _raise_must_copy
    clear = _raise_must_copy
    __iadd__ = _raise_must_copy
    __imul__ = _raise_must_copy
    append = _raise_must_copy
    extend = _raise_must_copy
    insert = _raise_must_copy
    pop = _raise_must_copy
    remove = _raise_must_copy
    reverse = _raise_must_copy
    sort = _raise_must_copy


class BaseConstantsMeta(type):
    def __setattr__(cls, attr, value):
        raise AttributeError("Constants are read-only.")

    def __new__(mcs, name, bases, attrs):

        for k, v in attrs.items():
            if type(v) == list:
                attrs[k] = ConstantsList(v)

        return super().__new__(mcs, name, bases, attrs)


class BaseConstants(metaclass=BaseConstantsMeta):
    @classmethod
    def get_normalized(cls, attr):
        if cls.__name__ == 'C':
            return getattr(cls, attr.upper())
        return getattr(cls, attr)


def get_roles(Constants) -> list:
    roles = []
    for k, v in Constants.__dict__.items():
        if k.upper().endswith('_ROLE') or k.upper().startswith('ROLE_'):
            if not isinstance(v, str):
                # this is especially for legacy apps before the role_* feature was introduced.
                msg = f"{k}: any Constant that ends with '_role' must be a string, for example: sender_role = 'Sender'"
                raise Exception(msg)
            roles.append(v)
    return roles


def get_role(roles, id_in_group):
    '''this is split apart from get_roles_ as a perf optimization'''
    if roles and len(roles) >= id_in_group:
        return roles[id_in_group - 1]
    return ''


get_param_truth_value = '1'
admin_secret_code = 'admin_secret_code'
timeout_happened = 'timeout_happened'
participant_label = 'participant_label'
wait_page_http_header = 'oTree-Wait-Page'
redisplay_with_errors_http_header = 'oTree-Redisplay-With-Errors'
field_required_msg = core_gettext('This field is required.')
AUTO_NAME_BOTS_EXPORT_FOLDER = 'auto_name'
ADVANCE_SLOWEST_BATCH_SIZE = 20
