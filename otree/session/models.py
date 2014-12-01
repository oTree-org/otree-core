import copy
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from otree.common_internal import id_label_name, add_params_to_url
from otree import constants
from otree.db import models
import otree.common_internal
from otree.common_internal import directory_name
from otree.common import Currency as c
from otree import constants

import django.test
from otree.models_concrete import SessionuserToUserLookup

class GlobalSingleton(models.Model):
    """object that can hold site-wide settings. There should only be one
    GlobalSingleton object. Also used for wait page actions.
    """

    # TODO: move to otree.models_concrete

    open_session = models.ForeignKey('Session', null=True, blank=True)

    admin_access_code = 'change_this'

    #FIXME: why do I get this after migrate? OperationalError: no such column: session_globalsingleton.admin_access_code
    """
    admin_access_code = models.RandomCharField(
        doc='''used for authentication to things only the admin/experimenter should access'''
    )
    """

    class Meta:
        verbose_name = 'Set open session'
        verbose_name_plural = verbose_name


class StubModel(models.Model):
    """To be used as the model for an empty form, so that form_class can be
    omitted. Consider using SingletonModel for this. Right now, I'm not
    sure we need it.

    """

    # TODO: move to otree.models_concrete

# R: You really need this only if you are using save_the_change,
#    which is not used for Session and SessionUser,
#    Otherwise you can just
def model_vars_default():
    return {}
class ModelWithVars(models.Model):
    vars = models.PickleField(default=model_vars_default)

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super(ModelWithVars, self).__init__(*args, **kwargs)
        self._old_vars = copy.deepcopy(self.vars)

    def save(self, *args, **kwargs):
        # Trick save_the_change to update vars
        if hasattr(self, '_changed_fields') and self.vars != self._old_vars:
            self._changed_fields['vars'] = self._old_vars
        super(ModelWithVars, self).save(*args, **kwargs)


class Session(ModelWithVars):

    class Meta:
        # if i don't set this, it could be in an unpredictable order
        ordering = ['pk']

    type_name = models.CharField(max_length = 300, null = True, blank = True,
        doc="the session type, as defined in the programmer's sessions.py."
    )

    def type(self):
        from otree.session import session_types_dict
        return session_types_dict()[self.type_name]

    # label of this session instance
    label = models.CharField(
        max_length = 300, null = True, blank = True,
        help_text = 'For internal record-keeping'
    )

    experimenter_name = models.CharField(
        max_length = 300, null = True, blank = True,
        help_text = 'For internal record-keeping'
    )


    code = models.RandomCharField(
        length=8, doc="Randomly generated unique identifier for the session."
    )

    money_per_point = models.DecimalField(decimal_places=5, max_digits=12)

    session_experimenter = models.OneToOneField(
        'SessionExperimenter', null=True, related_name='session',
    )

    time_scheduled = models.DateTimeField(
        null=True, doc="The time at which the session is scheduled",
        help_text = 'For internal record-keeping',
    )

    time_started = models.DateTimeField(
        null=True,
        doc="The time at which the experimenter started the session",
    )

    first_subsession_content_type = models.ForeignKey(
        ContentType, null=True, related_name = '%(app_label)s_%(class)s'
    )
    first_subsession_object_id = models.PositiveIntegerField(null=True)
    first_subsession = generic.GenericForeignKey(
        'first_subsession_content_type', 'first_subsession_object_id'
    )

    mturk_payment_was_sent = models.BooleanField(default=False)

    hidden = models.BooleanField(default=False)

    git_commit_timestamp = models.CharField(
        max_length=200, null=True, doc=(
            "Indicates the version of the code (as recorded by Git) that was "
            "used to run the session, so that the session can be replicated "
            "later.\n Search through the Git commit log to find a commit that "
            "was made at this time."
        )
    )

    # todo: change this to money
    fixed_pay = models.CurrencyField(doc="""Show-up fee""")

    comment = models.TextField()

    _players_assigned_to_groups = models.BooleanField(default=False)

    #
    special_category = models.CharField(max_length=20, null=True,
        doc="whether it's a test session, demo session, etc."
    )

    # whether someone already viewed this session's demo links
    demo_already_used = models.BooleanField(default=False)

    # indicates whether a session has been fully created (not only has the
    # model itself been created, but also the other models in the hierarchy)
    ready = models.BooleanField(default=False)

    def __unicode__(self):
        return self.code

    def is_open(self):
        return GlobalSingleton.objects.get().open_session == self


    def subsession_names(self):
        names = []
        for subsession in self.get_subsessions():
            app_label = subsession._meta.app_label
            name = '{} {}'.format(
                otree.common_internal.app_name_format(app_label),
                subsession.name()
            )
            names.append(name)
        if names:
            return ', '.join(names)
        else:
            return '[empty sequence]'

    def get_subsessions(self):
        lst = []
        subsession = self.first_subsession
        while True:
            if not subsession:
                break
            lst.append(subsession)
            subsession = subsession.next_subsession
        return lst

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

        participants = self.get_participants()
        num_participants = len(participants)

        subsessions = self.get_subsessions()

        first_subsession_players = self.first_subsession.get_players()

        for i in range(num_participants):
            player = first_subsession_players[i]
            participant = player.participant
            participant.me_in_first_subsession = player
            participant.save()

        for subsession_index in range(len(subsessions) - 1):
            players_left = subsessions[subsession_index].get_players()
            players_right = subsessions[subsession_index+1].get_players()
            players_right_dict = {p.participant.pk: p for p in players_right}
            for player_index in range(num_participants):
                player_left = players_left[player_index]
                player_right = players_right_dict[player_left.participant.pk]
                assert (
                    player_left.participant and
                    player_left.participant == player_right.participant
                )
                player_left._me_in_next_subsession = player_right
                player_right._me_in_previous_subsession = player_left
                player_left.save()
                player_right.save()

    def add_subsession(self, subsession):
        subsession.session = self
        subsession.save()

    def delete(self, using=None):
        for subsession in self.get_subsessions():
            subsession.delete()
        super(Session, self).delete(using)

    def get_participants(self):
        return self.participant_set.all()

    def payments_ready(self):
        for participants in self.get_participants():
            if not participants.payoff_from_subsessions_is_complete():
                return False
        return True
    payments_ready.boolean = True

    def _assign_groups_and_initialize(self):
        for subsession in self.get_subsessions():
            subsession._create_empty_groups()
            subsession._assign_groups()
            subsession._initialize()
        self._players_assigned_to_groups = True
        self.save()


    def advance_last_place_participants(self):
        participants = self.get_participants()


        c = django.test.Client()

        # in case some participants haven't started
        for p in participants:
            if not p.visited:
                c.get(p._start_url(), follow=True)

        last_place_page_index = min([p._index_in_pages for p in participants])
        last_place_participants = [p for p in participants if p._index_in_pages == last_place_page_index]

        for p in last_place_participants:
            # what if current_form_page_url hasn't been set yet?
            resp = c.post(p._current_form_page_url, data={constants.auto_submit: True}, follow=True)
            assert resp.status_code < 400

    def build_session_user_to_user_lookups(self):

        subsession_app_names = self.type().subsession_apps

        num_pages_in_each_app = {}
        for app_name in subsession_app_names:
            views_module = otree.common_internal.get_views_module(app_name)
            num_pages = len(views_module.pages())
            num_pages_in_each_app[app_name] = num_pages

        for participant in self.get_participants():
            participant.build_session_user_to_user_lookups(num_pages_in_each_app)

        # FIXME: what about experimenter?




class SessionUser(ModelWithVars):

    _index_in_subsessions = models.PositiveIntegerField(default=0, null=True)

    _index_in_pages = models.PositiveIntegerField(default=0)

    me_in_first_subsession_content_type = models.ForeignKey(
        ContentType, null=True, related_name = '%(app_label)s_%(class)s'
    )
    me_in_first_subsession_object_id = models.PositiveIntegerField(null=True)

    code = models.RandomCharField(
        length = 8, doc=(
            "Randomly generated unique identifier for the participant. If you "
            "would like to merge this dataset with those from another "
            "subsession in the same session, you should join on this field, "
            "which will be the same across subsessions."
        )
    )

    me_in_first_subsession = generic.GenericForeignKey(
        'me_in_first_subsession_content_type',
        'me_in_first_subsession_object_id'
    )

    last_request_succeeded = models.NullBooleanField(
        verbose_name='Health of last server request'
    )

    visited = models.BooleanField(default=False,
        doc="""Whether this user's start URL was opened"""
    )

    ip_address = models.GenericIPAddressField(null = True)

    # stores when the page was first visited
    _last_page_timestamp = models.DateTimeField(null=True)

    is_on_wait_page = models.BooleanField(default=False)

    current_page = models.CharField(max_length=200,null=True)

    _current_form_page_url = models.URLField()

    _current_user_code = models.CharField()
    _current_app_name = models.CharField()

    def _current_user(self):
        return self.get_users()[self._index_in_subsessions]

    def subsessions_completed(self):
        if not self.visited:
            return None
        return '{}/{} subsessions'.format(
            self._index_in_subsessions, len(self.session.get_subsessions())
        )

    def _pages_completed_in_current_subsession(self):
        return self._current_user()._pages_completed()

    def current_subsession(self):
        if not self.visited:
            return None
        subsssn = self.session.get_subsessions()[self._index_in_subsessions]
        app_label = subsssn._meta.app_label
        return otree.common_internal.app_name_format(app_label)

    def get_users(self):
        """Used to calculate payoffs"""
        lst = []
        me_in_next_subsession = self.me_in_first_subsession
        while True:
            if not me_in_next_subsession:
                break
            lst.append(me_in_next_subsession)
            me_in_next_subsession = (
                me_in_next_subsession._me_in_next_subsession
            )
        return lst

    def status(self):
        if self.is_on_wait_page:
            return 'Waiting'
        return ''

    def _pages_completed(self):
        if not self.visited:
            return None
        return '{}/{} pages'.format(
            self._index_in_pages,
            len(self._pages())
        )

    def _pages(self):
        from otree.views.concrete import WaitUntilAssignedToGroup

        pages = []
        for user in self.get_users():
            views_module = otree.common_internal.get_views_module(user._meta.app_label)
            subsession_pages = [WaitUntilAssignedToGroup] + views_module.pages()
            pages.extend(subsession_pages)
        return pages

    def _pages_as_urls(self):
        return [View.url(self, index) for index, View in enumerate(self._pages())]

    def build_session_user_to_user_lookups(self, num_pages_in_each_app):
        page_index = 0
        for user in self.get_users():
            app_name = user._meta.app_label
            for i in range(num_pages_in_each_app[app_name] + 1): # +1 is for WaitUntilAssigned...
                SessionuserToUserLookup(
                    session_user_pk=self.pk,
                    page_index=page_index,
                    app_name=app_name,
                    user_pk=user.pk,
                    is_experimenter = self._is_experimenter,
                ).save()
                page_index += 1

    class Meta:
        abstract = True






class SessionExperimenter(SessionUser):

    _is_experimenter = True

    def _start_url(self):
        return '/InitializeSessionExperimenter/{}/'.format(
            self.code
        )

    def chain_experimenters(self):
        subsessions = self.session.get_subsessions()

        self.me_in_first_subsession = subsessions[0]._experimenter
        self.save()

        for i in range(len(subsessions) - 1):
            left_experimenter = subsessions[i]._experimenter
            right_experimenter = subsessions[i+1]._experimenter
            left_experimenter._me_in_next_subsession = right_experimenter
            right_experimenter._me_in_previous_subsession = left_experimenter
        for subsession in subsessions:
            subsession._experimenter.session_experimenter = self
            subsession._experimenter.save()

    def experimenters(self):
        return self.get_users()



    user_type_in_url = constants.user_type_experimenter

class Participant(SessionUser):

    _is_experimenter = False

    class Meta:
        ordering = ['pk']

    exclude_from_data_analysis = models.BooleanField(
        default=False, doc=(
            "if set to 1, the experimenter indicated that this participant's "
            "data points should be excluded from the data analysis (e.g. a "
            "problem took place during the experiment)"
        )
    )

    session = models.ForeignKey(Session)

    time_started = models.DateTimeField(null=True)

    user_type_in_url = constants.user_type_participant

    mturk_assignment_id = models.CharField(max_length = 50, null = True)
    mturk_worker_id = models.CharField(max_length = 50, null = True)

    # unique=True can't be set, because the same external ID could be reused
    # in multiple sequences. however, it should be unique within the sequence.
    label = models.CharField(
        max_length = 50, null = True, doc=(
            "Label assigned by the experimenter. Can be assigned by passing a "
            "GET param called 'participant_label' to the participant's start "
            "URL"
        )
    )

    def __unicode__(self):
        return self.name()

    def _assign_to_groups(self):
        for p in self.get_players():
            p._assign_to_group()

    def _start_url(self):
        return '/InitializeParticipant/{}'.format(
            self.code
        )

    def get_players(self):
        return self.get_users()

    def payoff_from_subsessions(self):
        """convert to payment currency, since often this will need to be
        printed on the results page But then again, it's easy to just do the
        multiplication oneself.

        """
        return sum(player.payoff or c(0) for player in self.get_players())

    def total_pay(self):
        return self.session.fixed_pay + self.payoff_from_subsessions()

    def payoff_from_subsessions_display(self):
        complete = self.payoff_from_subsessions_is_complete()
        payoff_from_subsessions = self.payoff_from_subsessions().to_money(
            self.session
        )
        if complete:
            return payoff_from_subsessions
        return u'{} (incomplete)'.format(payoff_from_subsessions)

    payoff_from_subsessions_display.short_description = (
        'payoff from subsessions'
    )

    def payoff_from_subsessions_is_complete(self):
        return all(p.payoff is not None for p in self.get_players())

    def total_pay_display(self):
        complete = self.payoff_from_subsessions_is_complete()
        total_pay = self.total_pay().to_money(self.session)
        if complete:
            return total_pay
        return u'{} (incomplete)'.format(total_pay)

    def name(self):
        return id_label_name(self.pk, self.label)


