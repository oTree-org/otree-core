from django.db import models
import common
from common import Symbols
from urlparse import urljoin
from django.conf import settings

class BaseParticipant(models.Model):
    """
    Base class for all participants.
    """

    #__metaclass__ = abc.ABCMeta

    #: the participant's unique ID (and redemption code) that gets passed in the URL.
    #: This is generated automatically.
    #: we don't use the primary key because a user might try incrementing/decrementing it out of curiosity/malice,
    #: and end up affecting another participant
    code = common.RandomCharField(length = 8)

    #: nickname they enter when they start playing.
    #: not currently essential to any functionality.
    name = models.CharField(max_length = 50, null = True)

    #: just in case we need to look up a user's IP address at some point
    #: (e.g. to investigate an issue or debug)
    ip_address = models.IPAddressField(null = True)

    #: whether the user has visited our site at all
    has_visited = models.BooleanField()

    #: the ordinal position in which a participant joined a game. Starts at 0.
    index = models.PositiveIntegerField(null = True)

    mturk_assignment_id = models.CharField(max_length = 50, null = True)

    def start_url(self):
        return urljoin(settings.DOMAIN,
                       '/{}/GetTreatmentOrParticipant/?{}={}'.format(self.experiment.url_base,
                                                          Symbols.participant_code,
                                                          self.code))

    #@abc.abstractmethod
    def bonus(self):
        """
        Must be implemented by child classes.

        The bonus the ``Participant`` gets paid, in addition to their base pay.

        Should return None if the bonus cannot yet be determined.
        """
        raise NotImplementedError()

    def safe_bonus(self):
        try:
            return self.bonus()
        except:
            return None

    def total_pay(self):
        if self.bonus() is None:
            return None
        else:
            return self.match.treatment.base_pay + self.bonus()

    def __unicode__(self):
        return self.code

    class Meta:
        abstract = True

class ParticipantInTwoPersonAsymmetricGame(BaseParticipant):
    """A participant in a 2-participant asymmetric game"""
    
    def is_participant_1(self):
        return self.index == 0

    def is_participant_2(self):
        return self.index == 1

    def bonus(self):
        if self.is_participant_1():
            return self.match.participant_1_bonus()
        elif self.is_participant_2():
            return self.match.participant_2_bonus()  

    class Meta:
        abstract = True
