from importlib import import_module
forms_internal = import_module('ptree.forms_internal')

class Form(forms_internal.ParticipantModelForm):

    def initial_values(self):
        return super(Form, self).initial_values()

    def choices(self):
        return super(Form, self).choices()

    def labels(self):
        return super(Form, self).labels()

    def order(self):
        return super(Form, self).order()


class ExperimenterForm(forms_internal.ExperimenterModelForm):

    def initial_values(self):
        return super(ExperimenterForm, self).initial_values()

    def choices(self):
        return super(ExperimenterForm, self).choices()

    def labels(self):
        return super(ExperimenterForm, self).labels()

    def order(self):
        return super(ExperimenterForm, self).order()