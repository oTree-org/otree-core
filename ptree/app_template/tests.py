import ptree.test
import {{ app_name }}.views as views
from {{ app_name }}.utilities import ParticipantMixin, ExperimenterMixin

class ParticipantBot(ParticipantMixin, ptree.test.ParticipantBot):

    def play(self):
        pass

class ExperimenterBot(ExperimenterMixin, ptree.test.ExperimenterBot):

    def play(self):
        pass
