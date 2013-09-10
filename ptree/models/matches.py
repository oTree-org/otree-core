from django.db import models
from django.forms import ModelForm
from django import forms
from ptree.templatetags.ptreefilters import currency
import abc

class MatchManager(models.Manager):
    def next_open_match(self, request):
        """Get the next match that is accepting players.
        May raise a StopIteration exception if there are no open matches.
        """
        from ptree.views.abstract import SessionKeys
        matches = super(MatchManager, self).get_query_set().all()
        return (m for m in matches if m.treatment.code == request.session[SessionKeys.treatment_code] and m.is_ready_for_next_player()).next()

class BaseMatch(models.Model):
    """
    Base class for all Matches.
    
    "Match" is used in the sense of "boxing match".

    It's a particular instance of a game being played,
    and holds the results of that instance, i.e. what the score was, who got paid what.

    Example of a Match: "dictator game between users Alice & Bob, where Alice gave $0.50"

    If a piece of data is specific to a particular player, you should store it in a Player object instead.
    For example, in the Prisoner's Dilemma, each Player has to decide between "Cooperate" and "Compete".
    You should store these on the Player object as player.decision,
    NOT "match.player_1_decision" and "match.player_2_decision".

    The only exception is if the game is asymmetric, and player_1_decision and player_2_decision have different data types.
    """


    #__metaclass__ = abc.ABCMeta

    time_started = models.DateTimeField(auto_now_add = True)

    objects = MatchManager()

    #@abc.abstractmethod
    def is_ready_for_next_player(self):
        raise NotImplementedError()

    def is_full(self):
        return len(self.players()) >= self.treatment.players_per_match

    def is_completed(self):
        self.match.amount_offered != None

    # a bit of sugar
    def players(self):
        return self.player_set.all()

    
    class Meta:
        abstract = True
        verbose_name_plural = "matches"



class MatchTwoPlayerSequential(BaseMatch):
    player_1 = models.ForeignKey('Player', related_name = "games_as_player_1")
    player_2 = models.ForeignKey('Player', related_name = "games_as_player_2", null = True)

    class Meta:
        abstract = True

    def is_ready_for_next_player(self):
        return self.player_1 and self.player_1.is_finished_playing() and not self.player_2


class MatchOffer(BaseMatch):
    amount_offered = models.PositiveIntegerField(null = True) # amount the first player offers to second player

