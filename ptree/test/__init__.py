from importlib import import_module
client = import_module('ptree.test.client')

# public API

class ParticipantBot(client.ParticipantBot):

    def play(self):
        return super(ParticipantBot, self).play()

    def submit(self, ViewClass, param_dict=None):
        return super(ParticipantBot, self).submit(ViewClass, param_dict)

    def submit_with_invalid_input(self, ViewClass, param_dict=None):
        return super(ParticipantBot, self).submit_with_invalid_input(ViewClass, param_dict)

    @property
    def participant(self):
        return super(ParticipantBot, self).participant

    @property
    def match(self):
        return super(ParticipantBot, self).match

    @property
    def treatment(self):
        return super(ParticipantBot, self).treatment

    @property
    def subsession(self):
        return super(ParticipantBot, self).subsession


class ExperimenterBot(client.ExperimenterBot):

    @property
    def subsession(self):
        return super(ExperimenterBot, self).subsession

    def play(self):
        return super(ExperimenterBot, self).play()

    def submit(self, ViewClass, param_dict=None):
        return super(ExperimenterBot, self).submit(ViewClass, param_dict)

    def submit_with_invalid_input(self, ViewClass, param_dict=None):
        return super(ExperimenterBot, self).submit_with_invalid_input(ViewClass, param_dict)
