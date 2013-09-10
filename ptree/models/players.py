from django.db import models
import ptree.models.common
from django.forms import ModelForm, Form
from django import forms
import abc

class BasePlayer(models.Model):
    """
    Base class for all players.
    A Player is a person who participates in a Match.
    For example, a Dictator Game match has 2 Players.
    If a game does not involve interaction between players, 
    a match will only contain 1 player.

    A Player object should store any attributes that need to be stored for each Player in the match.
    """

    #__metaclass__ = abc.ABCMeta

    # the player's unique ID (and redemption code) that gets passed in the URL.
    # This is generated automatically.
    # we don't use the primary key because a user might try incrementing/decrementing it out of curiosity/malice,
    # and end up affecting another player
    code = ptree.models.common.RandomCharField(length = 8)

    # nickname they enter when they start playing.
    # not currently essential to any functionality.
    nickname = models.CharField(max_length = 50, null = True)

    # just in case we need to look up a user's IP address at some point
    # (e.g. to investigate an issue or debug)
    ip_address = models.IPAddressField(null = True)

    # whether the user has visited our site at all
    has_visited = models.BooleanField()

    # the ordinal position in which a player joined a game. Starts at 0.
    index = models.PositiveIntegerField(null = True)
    

    #@abc.abstractmethod
    def bonus(self):
        raise NotImplementedError()

    def total_pay(self):
        return self.match.treatment.base_pay + self.bonus()

    #@abc.abstractmethod
    def is_finished_playing(self):
        """
        FIXME: need to come up with a rigorous definition for this method.
        Useful for many things, in particular deciding if the game is ready for the next player
        What if the user has unblocked the other user but hasn't done all required tasks,
        like filling out the survey?
        Consider getting rid of this method or renaming it since it may be misused or cause confusion
        """
        raise NotImplementedError()

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

    def is_finished_playing(self):
        if self.is_player_1():
            return self.match.player_1_is_finished_playing()
        elif self.is_player_2():
            return self.match.player_2_is_finished_playing()
        
    class Meta:
        abstract = True  
