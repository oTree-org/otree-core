from django.db import models
from ptree.fields import RandomCharField
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from ptree.common import id_label_name, add_params_to_url
from ptree import constants
from ptree.common import currency

class StubModel(models.Model):
    """To be used as the model for an empty form, so that form_class can be omitted."""

class SequenceOfExperiments(models.Model):
    label = models.CharField(max_length = 300, null = True, blank = True)
    time_created = models.DateTimeField(auto_now_add = True)
    code = RandomCharField(length=8)
    experimenter_access_code = RandomCharField(length=8)
    first_experiment_content_type = models.ForeignKey(ContentType,
                                                      null=True,
                                                      related_name = '%(app_label)s_%(class)s')
    first_experiment_object_id = models.PositiveIntegerField(null=True)
    first_experiment = generic.GenericForeignKey('first_experiment_content_type',
                                            'first_experiment_object_id',)

    is_for_mturk = models.BooleanField(verbose_name='Is for MTurk', default=True)
    payment_was_sent = models.BooleanField(default=False)
    preassign_matches = models.BooleanField(default=False)

    # how much people are getting paid to perform it
    base_pay = models.PositiveIntegerField()

    def name(self):
        """Define this because Django-Inspect-Model (django-inspect-model.rtfd.org/en/latest/#usage)
        doesn't recognize the __unicode__ method, and Django-data-exports relies on this."""
        if self.name:
            return self.name

        if self.label:
            postfix = self.label
        else:
            experiment_names = []
            for experiment in self.experiments():
                experiment_names.append('{} {}'.format(experiment._meta.app_label, experiment))
            if experiment_names:
                postfix = ', '.join(experiment_names)
            else:
                postfix = '[empty sequence]'
        return '{}: {}'.format(self.pk, postfix)

    unicode.short_description = 'Name'

    def start_url(self):
        """The URL that a user is redirected to in order to start a treatment"""
        return '/InitializeSequence/?{}={}'.format(constants.sequence_of_experiments_code,
                                                   self.code)

    def experiments(self):
        lst = []
        experiment = self.first_experiment
        while True:
            if not experiment:
                break
            lst.append(experiment)
            experiment = experiment.next_experiment
        return lst


    def __unicode__(self):
        return self.unicode()

    def add_experiments(self, experiments):
        self.first_experiment = experiments[0]
        for i in range(len(experiments) - 1):
            experiments[i].next_experiment = experiments[i + 1]
            experiments[i + 1].previous_experiment = experiments[i]
        for experiment in experiments:
            experiment.sequence_of_experiments = self
            experiment.save()
        self.save()

    def connect_participants_between_experiments(self):
        """Should be called after add_experiments"""

        num_participants = len(self.participants())

        experiments = self.experiments()

        for experiment_index in range(len(experiments) - 1):
            participants_left = experiments[experiment_index].participants()
            participants_right = experiments[experiment_index + 1].participants()
            for participant_index in range(num_participants):
                participant_left = participants_left[participant_index]
                participant_right = participants_right[participant_index]
                participant_left.me_in_next_experiment = participant_right
                participant_right.me_in_previous_experiment = participant_left
                participant_left.save()
                participant_right.save()

    def participants(self):
        return self.participant_set.all()

    class Meta:
        verbose_name_plural = 'sequences of experiments'

class Participant(models.Model):

    sequence_of_experiments = models.ForeignKey(SequenceOfExperiments)

    me_in_first_experiment_content_type = models.ForeignKey(ContentType,
                                                      null=True,
                                                      related_name = '%(app_label)s_%(class)s')
    me_in_first_experiment_object_id = models.PositiveIntegerField(null=True)
    me_in_first_experiment = generic.GenericForeignKey('me_in_first_experiment_content_type',
                                                'me_in_first_experiment_object_id',)

    def participants(self):
        lst = []
        me_in_next_experiment = self.me_in_first_experiment
        while True:
            if not me_in_next_experiment:
                break
            lst.append(me_in_next_experiment)
            me_in_next_experiment = me_in_next_experiment.me_in_next_experiment
        return lst

    def bonus(self):
        try:
            return sum(participant.bonus() for participant in self.participants())
        except:
            return None

    def total_pay(self):
        try:
            return self.sequence_of_experiments.base_pay + self.bonus()
        except:
            return None

    def bonus_display(self):
        return currency(self.bonus())

    def total_pay_display(self):
        return currency(self.total_pay())

    visited = models.BooleanField(default=False)
    was_terminated = models.BooleanField(default=False)
    mturk_assignment_id = models.CharField(max_length = 50, null = True)
    mturk_worker_id = models.CharField(max_length = 50, null = True)
    ip_address = models.IPAddressField(null = True)

    # unique=True can't be set, because the same external ID could be reused in multiple sequences.
    # however, it should be unique within the sequence.
    label = models.CharField(max_length = 50,
                                   null = True)


    def name(self):
        return id_label_name(self.pk, self.label)

    def __unicode__(self):
        return self.name()

    class Meta:
        ordering = ['pk']

    def start_url(self):
        return '/InitializeSequence/?{}={}'.format(constants.participant_in_sequence_of_experiments_code,
                                           self.code)

def create_sequence(label, num_participants, is_for_mturk, preassign_matches, app_names):
    seq = SequenceOfExperiments(label, num_participants, is_for_mturk, preassign_matches)

    seq.save()

    participants_in_sequence_of_experiments = []
    for i in range(num_participants):
        participant = Participant(sequence_of_experiments = seq)
        participant.save()
        participants_in_sequence_of_experiments.append(participant)


    experiments = []
    for app_name in app_names:
        if app_name not in settings.INSTALLED_PTREE_APPS:
            print 'Before running this command you need to add "{}" to INSTALLED_PTREE_APPS.'.format(app_name)
            return

        models_module = import_module('{}.models'.format(app_name))
        experiment = models_module.create_experiment_and_treatments()
        for i in range(num_participants):
            participant = models_module.Participant(experiment = experiment,
                                                    participant_in_sequence_of_experiments = participants_in_sequence_of_experiments[i])
            participant.save()

        if seq.preassign_matches:
            participants = list(experiment.participants())
            random.shuffle(participants)
            for participant in participants:
                participant.treatment = experiment.pick_treatment_for_incoming_participant()
                ptree.views.abstract.configure_match(models_module.Match, participant)
                participant.save()

        print 'Created objects for {}'.format(app_name)
        experiments.append(experiment)


    seq.add_experiments(experiments)
    seq.connect_participants_between_experiments()