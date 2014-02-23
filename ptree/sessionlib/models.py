from ptree.db import models
from ptree.fields import RandomCharField
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from ptree.common import id_label_name, add_params_to_url
from ptree import constants
from ptree.common import currency
import ptree.common

class StubModel(models.Model):
    """To be used as the model for an empty form, so that form_class can be omitted."""

class Session(models.Model):
    label = models.CharField(max_length = 300, null = True, blank = True)
    code = RandomCharField(length=8)

    session_experimenter = models.OneToOneField(
        'SessionExperimenter',
        null=True,
        related_name='session',
    )

    first_subsession_content_type = models.ForeignKey(ContentType,
                                                      null=True,
                                                      related_name = '%(app_label)s_%(class)s')
    first_subsession_object_id = models.PositiveIntegerField(null=True)
    first_subsession = generic.GenericForeignKey('first_subsession_content_type',
                                            'first_subsession_object_id',)

    is_for_mturk = models.BooleanField(verbose_name='Is for MTurk', default=True)
    payment_was_sent = models.BooleanField(default=False)

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

    def subsession_names(self):
        names = []
        for subsession in self.subsessions():
            names.append('{} {}'.format(ptree.common.app_name_format(subsession._meta.app_label), subsession.name()))
        if names:
            return ', '.join(names)
        else:
            return '[empty sequence]'

    def start_url(self):
        """The URL that a user is redirected to in order to start a treatment"""
        return '/InitializeSessionParticipant/?{}={}'.format(constants.session_code,
                                                   self.code)

    def subsessions(self):
        lst = []
        subsession = self.first_subsession
        while True:
            if not subsession:
                break
            lst.append(subsession)
            subsession = subsession.next_subsession
        return lst


    def __unicode__(self):
        return self.name()

    def chain_subsessions(self, subsessions):
        self.first_subsession = subsessions[0]
        for i in range(len(subsessions) - 1):
            subsessions[i].next_subsession = subsessions[i + 1]
            subsessions[i + 1].previous_subsession = subsessions[i]
        for i, subsession in enumerate(subsessions):
            subsession.index_in_subsessions = i
            subsession.save()
        self.save()

    def chain_participants(self):
        """Should be called after add_subsessions"""

        seq_participants = self.participants()
        num_participants = len(seq_participants)

        subsessions = self.subsessions()

        first_subsession_participants = self.first_subsession.participants()

        for i in range(num_participants):
            seq_participants[i].me_in_first_subsession = first_subsession_participants[i]
            seq_participants[i].save()

        for subsession_index in range(len(subsessions) - 1):
            participants_left = subsessions[subsession_index].participants()
            participants_right = subsessions[subsession_index + 1].participants()
            for participant_index in range(num_participants):
                participant_left = participants_left[participant_index]
                participant_right = participants_right[participant_index]
                participant_left.me_in_next_subsession = participant_right
                participant_right.me_in_previous_subsession = participant_left
                participant_left.save()
                participant_right.save()

    def add_subsession(self, subsession):
        subsession.session = self
        subsession.save()
        for treatment in subsession.treatments():
            treatment.session = self
            treatment.save()

    def delete(self, using=None):
        for subsession in self.subsessions():
            subsession.delete()
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

class SessionUser(models.Model):

    index_in_subsessions = models.PositiveIntegerField(default=0, null=True)
    index_in_pages = models.PositiveIntegerField(default=0, null=True)

    me_in_first_subsession_content_type = models.ForeignKey(ContentType,
                                                      null=True,
                                                      related_name = '%(app_label)s_%(class)s')
    me_in_first_subsession_object_id = models.PositiveIntegerField(null=True)
    code = RandomCharField(length = 8)
    me_in_first_subsession = generic.GenericForeignKey('me_in_first_subsession_content_type',
                                                'me_in_first_subsession_object_id',)

    last_request_succeeded = models.NullBooleanField(verbose_name='Health of last server request')

    visited = models.BooleanField(default=False)
    ip_address = models.IPAddressField(null = True)
    time_started = models.DateTimeField(null=True)

    def subsessions_completed(self):
        if not self.visited:
            return None
        return '{}/{} subsessions'.format(self.index_in_subsessions, len(self.session.subsessions()))

    def pages_completed_in_current_subsession(self):
        try:
            return self.users()[self.index_in_subsessions].pages_completed()
        except:
            return '(Error)'

    def current_subsession(self):
        if not self.visited:
            return None
        try:
            return ptree.common.app_name_format(self.session.subsessions()[self.index_in_subsessions]._meta.app_label)
        except IndexError:
            return '(Error)'

    def users(self):
        """Used to calculate bonuses"""
        lst = []
        me_in_next_subsession = self.me_in_first_subsession
        while True:
            if not me_in_next_subsession:
                break
            lst.append(me_in_next_subsession)
            me_in_next_subsession = me_in_next_subsession.me_in_next_subsession
        return lst

    is_on_waiting_page = models.BooleanField(default=False)

    def status(self):
        if self.is_on_waiting_page:
            return 'Waiting'

    class Meta:
        abstract = True

class SessionExperimenter(SessionUser):
    def start_url(self):
        return '/InitializeSessionExperimenter/?{}={}'.format(
            constants.session_user_code,
            self.code
        )

    def chain_experimenters(self):
        subsessions = self.session.subsessions()

        self.me_in_first_subsession = subsessions[0].experimenter
        self.save()

        for i in range(len(subsessions) - 1):
            left_experimenter = subsessions[i].experimenter
            right_experimenter = subsessions[i+1].experimenter
            left_experimenter.me_in_next_subsession = right_experimenter
            right_experimenter.me_in_previous_subsession = left_experimenter
        for subsession in subsessions:
            subsession.experimenter.session_experimenter = self
            subsession.experimenter.save()

    def experimenters(self):
        return self.users()

    name_in_url = constants.experimenter_or_participant_experimenter

class SessionParticipant(SessionUser):

    exclude_from_data_analysis = models.BooleanField(default=False)

    session = models.ForeignKey(Session)

    name_in_url = constants.experimenter_or_participant_participant

    def start_url(self):
        return '/InitializeSessionParticipant/?{}={}'.format(constants.session_user_code,
                                           self.code)


    def participants(self):
        return self.users()

    def bonus(self):
        return sum(participant.bonus or 0 for participant in self.participants())

    def total_pay(self):
        try:
            return self.session.base_pay + self.bonus()
        except:
            return None

    def bonus_display(self):
        complete = self.bonus_is_complete()
        bonus = currency(self.bonus())
        if complete:
            return bonus
        return u'{} (incomplete)'.format(bonus)

    bonus_display.short_description = 'bonus'

    def bonus_is_complete(self):
        for p in self.participants():
            if p.bonus is None:
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


    mturk_assignment_id = models.CharField(max_length = 50, null = True)
    mturk_worker_id = models.CharField(max_length = 50, null = True)

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


