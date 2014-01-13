# Don't change anything in this file.
import {{ app_name }}.models
import ptree.views
import ptree.forms

class ViewInThisApp(object):
    """Keep this as is"""
    TreatmentClass = {{ app_name }}.models.Treatment
    MatchClass = {{ app_name }}.models.Match
    ParticipantClass = {{ app_name }}.models.Participant
    ExperimentClass = {{ app_name }}.models.Experiment

    def for_IDE_autocomplete(self):
        """
        never actually gets called :)
        only exists to declare frequently used instance vars,
        so that the IDE's IntelliSense/code completion finds these attributes
        to make writing code faster.
        """

        self.experiment = {{ app_name }}.models.Experiment()
        self.treatment = {{ app_name }}.models.Treatment()
        self.match = {{ app_name }}.models.Match()
        self.participant = {{ app_name }}.models.Participant()

class ModelFormInThisApp(object):
    def for_IDE_autocomplete(self):
        """
        never actually gets called :)
        only exists to declare frequently used instance vars,
        so that the IDE's IntelliSense/code completion finds these attributes
        to make writing code faster.
        """

        self.experiment = {{ app_name }}.models.Experiment()
        self.treatment = {{ app_name }}.models.Treatment()
        self.match = {{ app_name }}.models.Match()
        self.participant = {{ app_name }}.models.Participant()

class ModelForm():
    def for_IDE_autocomplete(self):
        self.experiment = {{ app_name }}.models.Experiment()
        self.treatment = {{ app_name }}.models.Treatment()
        self.match = {{ app_name }}.models.Match()
        self.participant = {{ app_name }}.models.Participant()

