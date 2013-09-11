from django.db import models
import ptree.models.common
from django.forms import ModelForm, Form
from django import forms
import abc

class BasePlayer(models.Model):
    """
    Base class for all players.
    """

    #__metaclass__ = abc.ABCMeta

    #: the player's unique ID (and redemption code) that gets passed in the URL.
    #: This is generated automatically.
    #: we don't use the primary key because a user might try incrementing/decrementing it out of curiosity/malice,
    #: and end up affecting another player
    code = ptree.models.common.RandomCharField(length = 8)

    #: nickname they enter when they start playing.
    #: not currently essential to any functionality.
    nickname = models.CharField(max_length = 50, null = True)

    #: just in case we need to look up a user's IP address at some point
    #: (e.g. to investigate an issue or debug)
    ip_address = models.IPAddressField(null = True)

    #: whether the user has visited our site at all
    has_visited = models.BooleanField()

    #: the ordinal position in which a player joined a game. Starts at 0.
    index = models.PositiveIntegerField(null = True)

    #: whether the player is finished playing (i.e. has seen the redemption code page)
    is_finished = models.BooleanField()
    

    #@abc.abstractmethod
    def bonus(self):
        """
        Must be implemented by child classes.

        The bonus the ``Player`` gets paid, in addition to their base pay.

        Should return None if the bonus cannot yet be determined.
        """
        raise NotImplementedError()

    def total_pay(self):
        """
        Returns (base pay + bonus), or None if bonus is not yet determined.
        """
        if self.bonus() == None:
            return None
        return self.match.treatment.base_pay + self.bonus()

    def __unicode__(self):
        return self.code

    class Meta:
        abstract = True

class PlayerTwoPersonAsymmetric(BasePlayer):
    """A player in a 2-player asymmetric game"""
    
    def is_player_1(self):
        return self.index == 0

    def is_player_2(self):
        return self.index == 1

    def bonus(self):
        if self.is_player_1():
            return self.match.player_1_bonus()
        elif self.is_player_2():
            return self.match.player_2_bonus()  

    def is_finished(self):
        if self.is_player_1():
            return self.match.player_1_is_finished()
        elif self.is_player_2():
            return self.match.player_2_is_finished()
        
    class Meta:
        abstract = True  
