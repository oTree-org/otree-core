import time
from collections import defaultdict
from typing import Iterable

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.template.defaultfilters import slugify
from django.utils.translation import ugettext_lazy as _
from otree.db import models as otreemodels
from django.db import models
from unidecode import unidecode


class UserManager(BaseUserManager):
    """Define a model manager for User model with no username field"""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """Create and save a User with the given email and password"""
        if not email:
            raise ValueError('Indtast venligst en email')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular User with the given email and password"""
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_field):
        """Create and save a SuperUser with the given email and password"""
        extra_field.setdefault('is_staff', True)
        extra_field.setdefault('is_superuser', True)

        if extra_field.get('is_staff') is not True:
            raise ValueError('SuperUser must have is_staff=True')
        if extra_field.get('is_superuser') is not True:
            raise ValueError('SuperUser must have is_superuser=True')

        return self._create_user(email, password, **extra_field)


class User(AbstractUser):
    """User Model"""

    username = None
    email = models.EmailField(_('email address'), unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()


class RoomsStorage(models.Model):
    """Rooms models class for creating rooms"""
    name = otreemodels.StringField(max_length=200, unique=True ,null=False)
    display_name = otreemodels.StringField(max_length=200)
    slug = models.SlugField(max_length=100)
    teacher = models.ForeignKey(User, db_column="username", on_delete=models.CASCADE, null=False)

    class Meta:
        verbose_name_plural = "Klasserum"
        index_together = [
            ("name", "slug"),
            ("name", "display_name"),
        ]
        ordering = ["-id"]

    def __str__(self):
        return f'{self.name}'

    def save(self, *args, **kwargs):
        self.slug = slugify(unidecode(self.name))
        super(RoomsStorage, self).save(*args, **kwargs)


class PageCompletion(models.Model):
    class Meta:
        app_label = "otree"

    app_name = models.CharField(max_length=300)
    page_index = models.PositiveIntegerField()
    page_name = models.CharField(max_length=300)
    # it needs a default, otherwise i get "added a non-nullable field without default"
    # eventually i can remove the default, if I am sure people did not skip over all
    # the intermediate versions.
    epoch_time = models.PositiveIntegerField(null=True)
    seconds_on_page = models.PositiveIntegerField()
    subsession_pk = models.PositiveIntegerField()
    participant = models.ForeignKey('otree.Participant', on_delete=models.CASCADE)
    session = models.ForeignKey('otree.Session', on_delete=models.CASCADE)
    auto_submitted = models.BooleanField()


class WaitPagePassage(models.Model):
    participant = models.ForeignKey('otree.Participant', on_delete=models.CASCADE)
    session = models.ForeignKey('otree.Session', on_delete=models.CASCADE)
    # don't set default=time.time because that's harder to patch
    epoch_time = models.PositiveIntegerField(null=True)
    # if False, means they exit the wait page
    is_enter = models.BooleanField()


class PageTimeout(models.Model):
    class Meta:
        app_label = "otree"
        index_together = ['participant', 'page_index']

    participant = models.ForeignKey('otree.Participant', on_delete=models.CASCADE)
    page_index = models.PositiveIntegerField()
    expiration_time = models.FloatField()


class CompletedGroupWaitPage(models.Model):
    class Meta:
        app_label = "otree"
        index_together = ['page_index', 'session', 'id_in_subsession']

    page_index = models.PositiveIntegerField()
    session = models.ForeignKey('otree.Session', on_delete=models.CASCADE)
    id_in_subsession = models.PositiveIntegerField(default=0)


class CompletedSubsessionWaitPage(models.Model):
    class Meta:
        app_label = "otree"
        index_together = ['page_index', 'session']

    page_index = models.PositiveIntegerField()
    session = models.ForeignKey('otree.Session', on_delete=models.CASCADE)


class ParticipantToPlayerLookup(models.Model):
    class Meta:
        app_label = "otree"
        index_together = ['participant', 'page_index']
        unique_together = ['participant', 'page_index']

    # TODO: add session code and round number, for browser bots?
    participant_code = models.CharField(max_length=20)
    participant = models.ForeignKey('otree.Participant', on_delete=models.CASCADE)
    page_index = models.PositiveIntegerField()
    app_name = models.CharField(max_length=300)
    player_pk = models.PositiveIntegerField()
    # can't store group_pk because group can change!
    subsession_pk = models.PositiveIntegerField()
    session_pk = models.PositiveIntegerField()
    url = models.CharField(max_length=300)


class ParticipantLockModel(models.Model):
    class Meta:
        app_label = "otree"

    participant_code = models.CharField(max_length=16, unique=True)

    locked = models.BooleanField(default=False)


class UndefinedFormModel(models.Model):
    """To be used as the model for an empty form, so that form_class can be
    omitted. Consider using SingletonModel for this. Right now, I'm not
    sure we need it.

    """

    class Meta:
        app_label = "otree"

    pass


class RoomToSession(models.Model):
    class Meta:
        app_label = "otree"

    room_name = models.CharField(unique=True, max_length=255)
    session = models.ForeignKey('otree.Session', on_delete=models.CASCADE)


class ParticipantRoomVisit(models.Model):
    class Meta:
        app_label = "otree"

    room_name = models.CharField(max_length=50)
    participant_label = models.CharField(max_length=200)
    tab_unique_id = models.CharField(max_length=20, unique=True)
    last_updated = models.FloatField()


class BrowserBotsLauncherSessionCode(models.Model):
    class Meta:
        app_label = "otree"

    code = models.CharField(max_length=10)

    # hack to enforce singleton
    is_only_record = models.BooleanField(unique=True, default=True)


class ChatMessage(models.Model):
    class Meta:
        index_together = ['channel', 'timestamp']

    # the name "channel" here is unrelated to Django channels
    channel = models.CharField(max_length=255)
    # related_name necessary to disambiguate with otreechat add on
    participant = models.ForeignKey(
        'otree.Participant', related_name='chat_messages_core', on_delete=models.CASCADE
    )
    nickname = models.CharField(max_length=255)

    # call it 'body' instead of 'message' or 'content' because those terms
    # are already used by channels
    body = models.TextField()
    timestamp = models.FloatField(default=time.time)


def add_time_spent_waiting(participants):
    session_passages_qs = WaitPagePassage.objects.filter(
        participant__in=participants
    ).order_by('id')
    _add_time_spent_waiting_inner(
        participants=participants, session_passages_qs=session_passages_qs
    )


def _add_time_spent_waiting_inner(
    *, participants, session_passages_qs: Iterable[WaitPagePassage]
):
    '''adds the attribute to each participant object so it can be shown in the template'''

    session_passages = defaultdict(list)
    for passage in session_passages_qs:
        session_passages[passage.participant_id].append(passage)

    for participant in participants:
        total = 0
        enter_time = None
        passages = session_passages.get(participant.id, [])
        for p in passages:
            if p.is_enter and not enter_time:
                enter_time = p.epoch_time
            if not p.is_enter and enter_time:
                total += p.epoch_time - enter_time
                enter_time = None
        # means they are still waiting
        if enter_time:
            total += time.time() - enter_time
        participant._is_frozen = False
        participant.waiting_seconds = int(total)



