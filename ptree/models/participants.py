from django.db import models
import common
import ptree.constants as constants
from urlparse import urljoin
from django.conf import settings
from ptree.templatetags.ptreefilters import currency

class BaseParticipant(models.Model):
    """
    Base class for all participants.
    """

    #: the participant's unique ID (and redemption code) that gets passed in the URL.
    code = common.RandomCharField(length = 8)

    name = models.CharField(max_length = 50, null = True)

    ip_address = models.IPAddressField(null = True)

    #: whether the user has visited our site at all
    has_visited = models.BooleanField(default=False)

    #: the ordinal position in which a participant joined a game. Starts at 0.
    index_among_participants_in_match = models.PositiveIntegerField(null = True)

    index_in_sequence_of_views = models.PositiveIntegerField(default=0)

    mturk_assignment_id = models.CharField(max_length = 50, null = True)
    mturk_worker_id = models.CharField(max_length = 50, null = True)

    def __unicode__(self):
        return str(self.pk)


    def start_url(self):
        return urljoin(settings.DOMAIN,
                       '/{}/GetTreatmentOrParticipant/?{}={}'.format(self.experiment.url_base,
                                                          constants.participant_code,
                                                          self.code))

    def bonus(self):
        """
        The bonus the participant gets paid, in addition to their base pay.

        Should return None if the bonus cannot yet be determined.
        """
        raise NotImplementedError()

    def bonus_display(self):
        """printable version of the bonus"""
        try:
            return currency(self.bonus())
        except:
            return None

    def total_pay_display(self):
        return currency(self.total_pay())

    def total_pay(self):
        try:
            bonus = self.bonus()
        except:
            bonus = None
        if bonus is None:
            return None
        else:
            return self.match.treatment.base_pay + bonus

    def __unicode__(self):
        return str(self.pk)

    class Meta:
        abstract = True

class ParticipantInTwoPersonAsymmetricGame(BaseParticipant):
    """A participant in a 2-participant asymmetric game"""
    
    def is_participant_1(self):
        return self.index_among_participants_in_match == 0

    def is_participant_2(self):
        return self.index_among_participants_in_match == 1

    def bonus(self):
        if self.is_participant_1():
            return self.match.participant_1_bonus()
        elif self.is_participant_2():
            return self.match.participant_2_bonus()  

    class Meta:
        abstract = True