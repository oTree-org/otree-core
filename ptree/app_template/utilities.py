# Don't change anything in this file.
import {{ app_name }}.models as models
import ptree.views
import ptree.forms

class ParticipantMixin(object):
    TreatmentClass = models.Treatment
    MatchClass = models.Match
    ParticipantClass = models.Participant
    SubsessionClass = models.Subsession

    def for_IDE_autocomplete(self):
        self.subsession = models.Subsession()
        self.treatment = models.Treatment()
        self.match = models.Match()
        self.participant = models.Participant()

class ExperimenterMixin(object):

    TreatmentClass = models.Treatment
    MatchClass = models.Match
    ParticipantClass = models.Participant
    SubsessionClass = models.Subsession

    def for_IDE_autocomplete(self):
        self.subsession = models.Subsession()

class InitializeParticipant(ParticipantMixin, ptree.views.InitializeParticipant):
    pass

class InitializeExperimenter(ExperimenterMixin, ptree.views.InitializeExperimenter):
    pass