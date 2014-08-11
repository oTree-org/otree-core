from importlib import import_module
forms_internal = import_module('otree.forms_internal')

class Form(forms_internal.PlayerModelForm):

    def defaults(self):
        return super(Form, self).defaults()

    def choices(self):
        return super(Form, self).choices()

    def labels(self):
        return super(Form, self).labels()

    def order(self):
        return super(Form, self).order()


class ExperimenterForm(forms_internal.ExperimenterModelForm):

    def defaults(self):
        return super(ExperimenterForm, self).defaults()

    def choices(self):
        return super(ExperimenterForm, self).choices()

    def labels(self):
        return super(ExperimenterForm, self).labels()

    def order(self):
        return super(ExperimenterForm, self).order()