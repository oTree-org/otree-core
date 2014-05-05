from importlib import import_module
forms_internal = import_module('ptree.forms_internal')


class _FormsPublicApiMixin(object):

    def initial_values(self):
        """Return a dict of any initial values"""
        return {}

    def choices(self):
        return {}

    def labels(self):
        return {}

    def order(self):
        pass

class Form(_FormsPublicApiMixin, forms_internal.ParticipantModelForm):
    pass

class ExperimenterForm(_FormsPublicApiMixin, forms_internal.ExperimenterModelForm):
    pass

__all__ = (
    'Form',
    'ExperimenterForm',
)