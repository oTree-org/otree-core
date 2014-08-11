from ptree.db import models
from ptree.fields import RandomCharField
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from ptree.common import id_label_name, add_params_to_url
from ptree import constants
from ptree.common import currency
import ptree.common
from ptree.common import directory_name
from django_extensions.db.fields.json import JSONField
from easymoney import Money

class Session(models.Model):

    #
    type_name = models.CharField(max_length = 300, null = True, blank = True,
        doc="""the session type, as defined in the programmer's session.py."""
    )

    def type(self):
        from ptree.session import session_types_as_dict
        return session_types_as_dict()[self.type_name]

    # label of this session instance
    label = models.CharField(max_length = 300, null = True, blank = True,
    )

    code = RandomCharField(
        length=8,
        doc="""
        Randomly generated unique identifier for the session.
        """
    )

    session_experimenter = models.OneToOneField(
        'SessionExperimenter',
        null=True,
        related_name='session',
    )

    time_started = models.DateTimeField(
        null=True,
        doc="""The time at which the experimenter started the session"""
    )

    first_subsession_content_type = models.ForeignKey(ContentType,
                                                      null=True,
                                                      related_name = '%(app_label)s_%(class)s')
    first_subsession_object_id = models.PositiveIntegerField(null=True)
    first_subsession = generic.GenericForeignKey('first_subsession_content_type',
                                            'first_subsession_object_id',)

    is_for_mturk = models.BooleanField(verbose_name='Is for MTurk', default=True)
    mturk_payment_was_sent = models.BooleanField(default=False)

    hidden = models.BooleanField(default=False)

    git_commit_timestamp = models.CharField(
        max_length=200,
        null=True,
        doc="""
        Indicates the version of the code (as recorded by Git) that was used to run the session, so that the session can be replicated later.
        Search through the Git commit log to find a commit that was made at this time.
        """

    )

    #
    base_pay = models.MoneyField(
        doc="""Show-up fee"""
    )

    comment = models.TextField()

    _players_assigned_to_matches = models.BooleanField(default=False)

    def base_pay_display(self):
        return currency(self.base_pay)

    base_pay_display.short_description = 'Base pay'

    #
    special_category = models.CharField(max_length=20, null=True,
        doc="""whether it's a test session, demo session, etc."""
    )

    # whether someone already viewed this session's demo links
    demo_already_used = models.BooleanField(default=False)

    # indicates whether a session has been fully created (not only has the model itself been created, but also the other models in the hierarchy)
    ready = models.BooleanField(default=False)

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
            subsession._index_in_subsessions = i
            subsession.save()
        self.save()

    def chain_players(self):
        """Should be called after add_subsessions"""

        session_participanRENAMEts = self.session_participanRENAMEts()
        num_session_participanRENAMEts = len(session_participanRENAMEts)

        subsessions = self.subsessions()

        first_subsession_participanRENAMEts = self.first_subsession.session_participanRENAMEts()

        for i in range(num_session_participanRENAMEts):
            session_participanRENAMEts[i].me_in_first_subsession = first_subsession_participanRENAMEts[i]
            session_participanRENAMEts[i].save()

        for subsession_index in range(len(subsessions) - 1):
            players_left = subsessions[subsession_index].players()
            players_right = subsessions[subsession_index + 1].players()
            for player_index in range(num_session_participanRENAMEts):
                player_left = players_left[player_index]
                player_right = players_right[player_index]
                player_left.me_in_next_subsession = player_right
                player_right.me_in_previous_subsession = player_left
                player_left.save()
                player_right.save()

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

    def session_participanRENAMEts(self):
        return self.SessionParticipanRENAMEt_set.all()

    def payments_ready(self):
        for session_participanRENAMEts in self.session_participanRENAMEts():
            if not session_participanRENAMEts.payoff_from_subsessions_is_complete():
                return False
        return True
    payments_ready.boolean = True

    def _assign_players_to_matches(self):
        for subsession in self.subsessions():
            subsession._create_empty_matches()
            subsession._assign_players_to_matches()
        self._players_assigned_to_matches = True
        self.save()

    class Meta:
        # if i don't set this, it could be in an unpredictable order
        ordering = ['pk']

class SessionUser(models.Model):

    _index_in_subsessions = models.PositiveIntegerField(default=0, null=True)

    me_in_first_subsession_content_type = models.ForeignKey(ContentType,
                                                      null=True,
                                                      related_name = '%(app_label)s_%(class)s')
    me_in_first_subsession_object_id = models.PositiveIntegerField(null=True)

    code = RandomCharField(
        length = 8,
        doc="""Randomly generated unique identifier for the session_participanRENAMEt.
        If you would like to merge this dataset with those from another subsession in the same session,
        you should join on this field, which will be the same across subsessions."""
    )

    me_in_first_subsession = generic.GenericForeignKey('me_in_first_subsession_content_type',
                                                'me_in_first_subsession_object_id',)

    last_request_succeeded = models.NullBooleanField(verbose_name='Health of last server request')

    visited = models.BooleanField(default=False,
        doc="""Whether this user's start URL was opened"""
    )

    ip_address = models.IPAddressField(null = True)


    is_on_wait_page = models.BooleanField(default=False)

    current_page = models.CharField(max_length=200,null=True)

    vars = JSONField()

    def subsessions_completed(self):
        if not self.visited:
            return None
        return '{}/{} subsessions'.format(self._index_in_subsessions, len(self.session.subsessions()))

    def _pages_completed_in_current_subsession(self):
        return self._users()[self._index_in_subsessions]._pages_completed()

    def current_subsession(self):
        if not self.visited:
            return None
        return ptree.common.app_name_format(self.session.subsessions()[self._index_in_subsessions]._meta.app_label)

    def _users(self):
        """Used to calculate payoffs"""
        lst = []
        me_in_next_subsession = self.me_in_first_subsession
        while True:
            if not me_in_next_subsession:
                break
            lst.append(me_in_next_subsession)
            me_in_next_subsession = me_in_next_subsession.me_in_next_subsession
        return lst

    def status(self):
        if self.is_on_wait_page:
            return 'Waiting'
        return ''

    def get_success_url(self):
        from ptree.views.concrete import RedirectToPageUserShouldBeOn
        return RedirectToPageUserShouldBeOn.url(self)


    class Meta:
        abstract = True

class SessionExperimenter(SessionUser):
    def _start_url(self):
        return '/InitializeSessionExperimenter/{}/'.format(
            self.code
        )

    def chain_experimenters(self):
        subsessions = self.session.subsessions()

        self.me_in_first_subsession = subsessions[0]._experimenter
        self.save()

        for i in range(len(subsessions) - 1):
            left_experimenter = subsessions[i]._experimenter
            right_experimenter = subsessions[i+1]._experimenter
            left_experimenter.me_in_next_subsession = right_experimenter
            right_experimenter.me_in_previous_subsession = left_experimenter
        for subsession in subsessions:
            subsession._experimenter.session_experimenter = self
            subsession._experimenter.save()

    def experimenters(self):
        return self._users()

    user_type_in_url = constants.user_type_experimenter

class SessionParticipanRENAMEt(SessionUser):

    exclude_from_data_analysis = models.BooleanField(default=False,
        doc="""
        if set to 1, the experimenter indicated that this session_participanRENAMEt's data points should be excluded from
        the data analysis (e.g. a problem took place during the experiment)"""

    )

    session = models.ForeignKey(Session)

    time_started = models.DateTimeField(null=True)

    user_type_in_url = constants.user_type_session_participanRENAMEt

    def _start_url(self):
        return '/InitializeSessionParticipanRENAMEt/{}'.format(
            self.code
        )

    def players(self):
        return self._users()

    def payoff_from_subsessions(self):
        return sum(player.payoff or Money(0) for player in self.players())

    def total_pay(self):
        try:
            return self.session.base_pay + self.payoff_from_subsessions()
        except:
            return None

    def payoff_from_subsessions_display(self):
        complete = self.payoff_from_subsessions_is_complete()
        payoff_from_subsessions = currency(self.payoff_from_subsessions())
        if complete:
            return payoff_from_subsessions
        return u'{} (incomplete)'.format(payoff_from_subsessions)

    payoff_from_subsessions_display.short_description = 'payoff from subsessions'

    def payoff_from_subsessions_is_complete(self):
        return all(p.payoff is not None for p in self.players())

    def total_pay_display(self):
        try:
            complete = self.payoff_from_subsessions_is_complete()
            total_pay = currency(self.total_pay())
        except:
            return 'Error in payoff calculation'
        if complete:
            return total_pay
        return u'{} (incomplete)'.format(total_pay)

    def _assign_to_matches(self):
        for p in self.players():
            p._assign_to_match()

    mturk_assignment_id = models.CharField(max_length = 50, null = True)
    mturk_worker_id = models.CharField(max_length = 50, null = True)

    # unique=True can't be set, because the same external ID could be reused in multiple sequences.
    # however, it should be unique within the sequence.
    label = models.CharField(
        max_length = 50,
        null = True,
        doc="""Label assigned by the experimenter. Can be assigned by passing a GET param called "session_participanRENAMEt_label" to the session_participanRENAMEt's start URL"""
    )

    def name(self):
        return id_label_name(self.pk, self.label)

    def __unicode__(self):
        return self.name()

    class Meta:
        ordering = ['pk']

class GlobalData(models.Model):
    """object that can hold site-wide properties. There should only be one GlobalData object.
    """
    open_session = models.ForeignKey(Session, null=True)

class StubModel(models.Model):
    """To be used as the model for an empty form, so that form_class can be omitted.
    Consider using SingletonModel for this. Right now, I'm not sure we need it.
    """
