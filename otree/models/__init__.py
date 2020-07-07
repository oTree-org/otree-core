# it's OK to do this because we have .pyi files

from django.db.models.signals import class_prepared

from otree.db.models import *  # noqa

from otree.models.subsession import BaseSubsession
from otree.models.group import BaseGroup
from otree.models.player import BasePlayer
from otree.models.session import Session
from otree.models.participant import Participant


def ensure_required_fields(sender, **kwargs):
    """
    Some models need to hook up some dynamically created fields. They can be
    created on the fly or might be defined by the user in the app directly.

    We use this signal handler to ensure that these fields exist and are
    created on demand.
    """
    if hasattr(sender, '_ensure_required_fields'):
        sender._ensure_required_fields()


class_prepared.connect(ensure_required_fields)
