from ptree.db import models
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
import sys

class StubModel(models.Model):
    """To be used as the model for an empty form, so that form_class can be omitted."""

class Session(models.Model):
    label = models.CharField(max_length = 300, null = True, blank = True)
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

    git_hash = models.CharField(max_length=200, null=True)

    # how much people are getting paid to perform it
    base_pay = models.PositiveIntegerField()

    comment = models.TextField()

    def base_pay_display(self):
        return currency(self.base_pay)

    base_pay_display.short_description = 'Base pay'

    def name(self):
        return id_label_name(self.pk, self.label)

    def experiment_names(self):
        names = []
        for experiment in self.experiments():
            names.append('{} {}'.format(ptree.common.app_name_format(experiment._meta.app_label), experiment.name()))
        if names:
            return ', '.join(names)
        else:
            return '[empty sequence]'

    def start_url(self):
        """The URL that a user is redirected to in order to start a treatment"""
        return '/InitializeSessionParticipant/?{}={}'.format(constants.session_code,
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
        for i, experiment in enumerate(experiments):
            experiment.index_in_sequence_of_experiments = i
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
        experiment.session = self
        experiment.save()
        for treatment in experiment.treatments():
            treatment.session = self
            treatment.save()

    def delete(self, using=None):
        for experiment in self.experiments():
            experiment.delete()
        super(Session, self).delete(using)

    def participants(self):
        return self.sessionparticipant_set.all()

    def payments_ready(self):
        try:
            for participant in self.participants():
                if not participant.bonus_is_complete():
                    return False
            return True
        except:
            return None
    payments_ready.boolean = True

    def time_started(self):
        start_times = [p.time_started for p in self.participants() if p.time_started is not None]
        if len(start_times) == 0:
            return None
        return sorted(start_times)[0]

    class Meta:
        ordering = ['pk']

class SessionParticipant(models.Model):

    session = models.ForeignKey(Session)

    index_in_sequence_of_experiments = models.PositiveIntegerField(default=0)

    me_in_first_experiment_content_type = models.ForeignKey(ContentType,
                                                      null=True,
                                                      related_name = '%(app_label)s_%(class)s')
    me_in_first_experiment_object_id = models.PositiveIntegerField(null=True)
    code = RandomCharField(length = 8)
    me_in_first_experiment = generic.GenericForeignKey('me_in_first_experiment_content_type',
                                                'me_in_first_experiment_object_id',)

    exclude_from_data_analysis = models.BooleanField(default=False)

    experimenter_comment = models.TextField()
    visited = models.BooleanField(default=False)

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
        if not self.visited:
            return None
        return '{}/{} experiments'.format(self.index_in_sequence_of_experiments + 1, len(self.session.experiments()))

    def current_experiment(self):
        if not self.visited:
            return None
        try:
            return ptree.common.app_name_format(self.session.experiments()[self.index_in_sequence_of_experiments]._meta.app_label)
        except IndexError: #FIXME: understand under what conditions this occurs
            return 'after {}'.format(ptree.common.app_name_format(self.session.experiments()[-1]._meta.app_label))

    def progress_in_current_experiment(self):
        try:
            return self.participants()[self.index_in_sequence_of_experiments].progress()
        except:
            return '(Error)'

    def bonus(self):
        return sum(participant.bonus() or 0 for participant in self.participants())

    def total_pay(self):
        try:
            return self.session.base_pay + self.bonus()
        except:
            return None

    def bonus_display(self):
        try:
            complete = self.bonus_is_complete()
            bonus = currency(self.bonus())
        except:
            return 'Error in bonus calculation'
        if complete:
            return bonus
        return u'{} (incomplete)'.format(bonus)

    bonus_display.short_description = 'bonus'

    def bonus_is_complete(self):
        for p in self.participants():
            if p.bonus() is None:
                return False
        return True

    def total_pay_display(self):
        try:
            complete = self.bonus_is_complete()
            total_pay = currency(self.total_pay())
        except:
            return 'Error in bonus calculation'
        if complete:
            return total_pay
        return u'{} (incomplete)'.format(total_pay)

    time_started = models.DateTimeField(null=True)
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
        return '/InitializeSessionParticipant/?{}={}'.format(constants.session_participant_code,
                                           self.code)

def create_session(label, is_for_mturk, preassign_matches, sequence, base_pay, num_participants):
    session = Session(label=label,
                                is_for_mturk=is_for_mturk,
                                preassign_matches=preassign_matches,
                                base_pay=base_pay)

    session.save()

    try:
        session_participants = []
        for i in range(num_participants):
            participant = SessionParticipant(session = session)
            participant.save()
            session_participants.append(participant)


        experiments = []
        for app_name in sequence:
            if app_name not in settings.INSTALLED_PTREE_APPS:
                print 'Before running this command you need to add "{}" to INSTALLED_PTREE_APPS.'.format(app_name)
                return

            models_module = import_module('{}.models'.format(app_name))
            experiment = models_module.create_experiment_and_treatments()
            experiment.save()
            session.add_experiment(experiment)
            for i in range(num_participants):
                participant = models_module.Participant(experiment = experiment,
                                                        session = session,
                                                        session_participant = session_participants[i])
                participant.save()

            if session.preassign_matches:
                participants = list(experiment.participants())
                random.shuffle(participants)
                for participant in participants:
                    participant.treatment = experiment.pick_treatment_for_incoming_participant()
                    ptree.common.assign_participant_to_match(models_module.Match, participant)
                    participant.save()

            # check that bonus calculation doesn't throw an error, to prevent downstream problems
            for participant in experiment.participants():
                exception = False
                wrong_type = False
                bonus = None
                try:
                    bonus = participant.bonus()
                except:
                    exception = True
                else:
                    if (not isinstance(bonus, int)) and bonus != None:
                        wrong_type = True
                if exception or wrong_type:
                    print '{}: participant.bonus() must either return an integer, or None if it cannot be calculated yet.'.format(app_name)
                    if wrong_type:
                        print 'Currently, the return value is {}'.format(bonus)
                    elif exception:
                        print 'Currently, it raises an exception.'
                    sys.exit(1)


            print 'Created objects for {}'.format(app_name)
            experiments.append(experiment)


        session.chain_experiments(experiments)
        session.chain_participants()
    except:
        session.delete()
        raise