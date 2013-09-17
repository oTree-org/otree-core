from django.http import HttpResponseRedirect
from django.db import models
import ptree.models.common
import abc

class BaseTreatment(models.Model):
    """
    Base class for all Treatments.
    Example of a treatment:
    'dictator game with stakes of $1, where participants have to chat with each other first'
    It's the definition of what everyone in the treatment group has to do.
    A treatment is defined before the experiment starts.
    Results of a game are not stored in ther Treatment object, they are stored in Match or Participant objects.
    """

    #__metaclass__ = abc.ABCMeta

    description = models.TextField(max_length = 1000, null = True, blank = True)

    # the treatment code in the URL. This is generated automatically.
    # we don't use the primary key because a user might try incrementing/decrementing it out of curiosity/malice,
    # and end up in the wrong treatment
    code = ptree.models.common.RandomCharField(length=8)
        
    base_pay = models.PositiveIntegerField() # how much people are getting paid to perform it


    participants_per_match = None


    def start_url(self):
        """The URL that a user is redirected to in order to start a treatment"""
        return '/{}/Start/'.format(self.experiment.url_base, self.code)
    
    def __unicode__(self):
        s = self.code
        if self.description:
            s += ' ({})'.format(self.description)
        return s

    def matches(self):
        """Syntactic sugar"""
        return self.match_set.all()

    #@abc.abstractmethod
    def sequence(self):
        """
        Returns a list of all the View classes that the user gets routed through sequentially.
        (Not all pages have to be displayed for all participants; see the is_displayed method)
        
        Example:
        import donation.views as views
        import ptree.views.concrete
        return [views.Start,
                ptree.views.concrete.AssignParticipantAndMatch,
                views.IntroPage,
                views.EnterOfferEncrypted, 
                views.ExplainRandomizationDetails, 
                views.EnterDecryptionKey,
                views.NotifyOfInvalidEncryptedDonation,
                views.EnterOfferUnencrypted,
                views.NotifyOfShred,
                views.Survey,
                views.RedemptionCode]

        """
        raise NotImplementedError()

    def sequence_as_urls(self):
        """Converts the sequence to URLs.

        e.g.:
        sequence() returns something like [views.IntroPage, ...]
        sequence_as_urls() returns something like ['mygame/IntroPage', ...]
        """
        return [view.url() for view in self.sequence()]

    class Meta:
        abstract = True


class OfferTreatment(BaseTreatment):
    """Use this treatment if your game requires a participant to offer money.
    
    Examples: 
    - dictator game
    - ultimatum game
    - public goods game
    - donation game
    - grading game
    
    The maximum offer and increment are customizable.
    """

    max_offer_amount = models.PositiveIntegerField(default=50)
    increment_amount = models.PositiveIntegerField(default=5) # the increment people get to choose.

    def offer_choices(self):
       """A list of integers with the amounts the participant can choose to offer.
       Example: [0, 10, 20, 30, 40, 50]"""
       return range(0, self.max_offer_amount + 1, self.increment_amount)

    def is_valid_offer(self, amount):
        return amount in self.offer_choices()

    class Meta:
        abstract = True
