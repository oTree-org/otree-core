from django.utils.translation import ugettext_lazy


class MustCopyError(Exception):
    pass


def _raise_must_copy(*args, **kwargs):
    msg = (
        "Cannot modify a list that originated in Constants. "
        "First, you must make a copy of it, for example: "
        "'my_list = Constants.my_list.copy()' "
        "or "
        "'self.participant.vars['my_list'] = Constants.my_list.copy()'. "
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
    pass


get_param_truth_value = '1'
admin_secret_code = 'admin_secret_code'
timeout_happened = 'timeout_happened'
participant_label = 'participant_label'
wait_page_http_header = 'oTree-Wait-Page'
redisplay_with_errors_http_header = 'oTree-Redisplay-With-Errors'
field_required_msg = ugettext_lazy('This field is required.')
AUTO_NAME_BOTS_EXPORT_FOLDER = 'auto_name'