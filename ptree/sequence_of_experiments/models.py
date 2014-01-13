from django.db import models
from ptree.fields import RandomCharField
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from ptree.common import id_label_name, add_params_to_url
from ptree import constants
from ptree.common import currency
from django.conf import settings
import random
import ptree.common
from django.utils.importlib import import_module

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

    hidden = models.BooleanField(default=False)

    # how much people are getting paid to perform it
    base_pay = models.PositiveIntegerField()

    comment = models.TextField()

    def name(self):
        return id_label_name(self.pk, self.label)

    def experiment_names(self):
        names = []
        for experiment in self.experiments():
            names.append('{} {}'.format(experiment._meta.app_label, experiment))
        if names:
            return ', '.join(names)
        else:
            return '[empty sequence]'

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
        return self.name()

    def chain_experiments(self, experiments):
        self.first_experiment = experiments[0]
        for i in range(len(experiments) - 1):
            experiments[i].next_experiment = experiments[i + 1]
            experiments[i + 1].previous_experiment = experiments[i]
        for experiment in experiments:
            experiment.save()
        self.save()

    def chain_participants(self):
        """Should be called after add_experiments"""

        seq_participants = self.participants()
        num_participants = len(seq_participants)

        experiments = self.experiments()

        first_experiment_participants = self.first_experiment.participants()

        for i in range(num_participants):
            seq_participants[i].me_in_first_experiment = first_experiment_participants[i]
            seq_participants[i].save()

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

    def add_experiment(self, experiment):
        experiment.sequence_of_experiments = self
        experiment.save()
        for treatment in experiment.treatments():
            treatment.sequence_of_experiments = self
            treatment.save()

    def delete(self, using=None):
        for experiment in self.experiments():
            experiment.delete()
        super(SequenceOfExperiments, self).delete(using)

    def participants(self):
        return self.participant_set.all()

    def payments_file_is_ready(self):
        for participant in self.participants():
            if not participant.bonus_is_complete():
                return False
        return True

    def time_started(self):
        try:
            return sorted(p.time_started for p in self.participants())[0]
        except IndexError:
            return None

    class Meta:
        verbose_name_plural = 'sequences of experiments'
        ordering = ['pk']

class Participant(models.Model):

    sequence_of_experiments = models.ForeignKey(SequenceOfExperiments)

    index_in_sequence_of_experiments = models.PositiveIntegerField(default=0)

    me_in_first_experiment_content_type = models.ForeignKey(ContentType,
                                                      null=True,
                                                      related_name = '%(app_label)s_%(class)s')
    me_in_first_experiment_object_id = models.PositiveIntegerField(null=True)
    code = RandomCharField(length = 8)
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

    def progress(self):
        return '{}/{} experiments'.format(self.index_in_sequence_of_experiments, len(self.sequence_of_experiments.experiments()))

    def bonus(self):
        return sum(participant.bonus() or 0 for participant in self.participants())

    def total_pay(self):
        try:
            return self.sequence_of_experiments.base_pay + self.bonus()
        except:
            return None

    def bonus_display(self):
        if self.bonus_is_complete():
            return currency(self.bonus())
        return u'{} (incomplete)'.format(currency(self.bonus()))

    def bonus_is_complete(self):
        for p in self.participants():
            if p.bonus() is None:
                return False
        return True

    def total_pay_display(self):
        if self.bonus_is_complete():
            return currency(self.total_pay())
        return '{} (incomplete)'.format(currency(self.total_pay()))

    time_started = models.DateTimeField(null=True)
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

def create_sequence(label, is_for_mturk, preassign_matches, app_names, base_pay, num_participants):
    seq = SequenceOfExperiments(label=label,
                                is_for_mturk=is_for_mturk,
                                preassign_matches=preassign_matches,
                                base_pay=base_pay)

    seq.save()

    try:
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
            seq.add_experiment(experiment)
            for i in range(num_participants):
                participant = models_module.Participant(experiment = experiment,
                                                        sequence_of_experiments = seq,
                                                        participant_in_sequence_of_experiments = participants_in_sequence_of_experiments[i])
                participant.save()

            if seq.preassign_matches:
                participants = list(experiment.participants())
                random.shuffle(participants)
                for participant in participants:
                    participant.treatment = experiment.pick_treatment_for_incoming_participant()
                    ptree.common.assign_participant_to_match(models_module.Match, participant)
                    participant.save()

            print 'Created objects for {}'.format(app_name)
            experiments.append(experiment)


        seq.chain_experiments(experiments)
        seq.chain_participants()
    except:
        seq.delete()
        raise