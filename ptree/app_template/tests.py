import ptree.test
import {{ app_name }}.views as views
from {{ app_name }}.utilities import ParticipantMixIn, ExperimenterMixIn

class ParticipantBot(ParticipantMixIn, ptree.test.ParticipantBot):

    def play(self):
        pass

class ExperimenterBot(ExperimenterMixIn, ptree.test.ExperimenterBot):

    def play(self):
        pass
