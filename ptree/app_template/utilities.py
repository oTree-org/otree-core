# Don't change anything in this file.
import {{ app_name }}.models as models
import ptree.views
import ptree.forms

class InThisApp(object):
    """Keep this as is"""
    TreatmentClass = models.Treatment
    MatchClass = models.Match
    ParticipantClass = models.Participant
    SubsessionClass = models.Subsession

    def for_IDE_autocomplete(self):
        """
        never actually gets called.
        only exists to declare frequently used instance vars,
        so that the IDE's IntelliSense/code completion finds these attributes
        to make writing code faster.
        """

        self.subsession = models.Subsession()
        self.treatment = models.Treatment()
        self.match = models.Match()
        self.participant = models.Participant()