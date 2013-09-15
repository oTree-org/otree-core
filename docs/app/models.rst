models.py
*******************

(For background, read about Django models `here <https://docs.djangoproject.com/en/dev/topics/db/models/>`_.)

Every pTree app needs 4 core models:

- Player
- Match
- Treatment
- Experiment

They are related to each other as follows:

A ``Player`` is part of a ``Match``, which is part of a ``Treatment``, which is part of an ``Experiment``.

Furthermore, there are usually multiple ``Player`` objects in a ``Match``, 
multiple ``Match`` objects in a ``Treatment``, 
and multiple ``Treatment`` objects in an ``Experiment``, meaning that your objects would look something like this:

.. image:: model-hierarchy.png

Player
~~~~~~
A ``Player`` is a person who participates in a ``Match``.
For example, a Dictator Game match has 2 ``Player`` objects.

A match can contain only 1 ``Player`` if there is no interaction between ``Player`` objects.
For example, a game that is simply a survey.

A ``Player`` object should store any attributes that need to be stored for each Player in the match.



Implementation
______________

``Player`` classes should inherit from ``ptree.models.players.BasePlayer``. Here is the class structure:

.. py:class:: Player

    .. py:method:: bonus(self)
    
        *You must implement this method.*

        The bonus the ``Player`` gets paid, in addition to their base pay.
    
    .. py:attribute:: code = ptree.models.common.RandomCharField(length = 8)
    
        the player's unique ID (and redemption code) that gets passed in the URL.
        This is generated automatically.
        
    .. py:attribute:: has_visited = models.BooleanField()
    
        whether the user has visited our site at all.
    
    .. py:attribute:: index = models.PositiveIntegerField(null = True)
    
        the ordinal position in which a player joined a game. Starts at 0.
    
    .. py:attribute:: is_finished = models.BooleanField()
    
        whether the player is finished playing (i.e. has seen the redemption code page).

        
           
Match
~~~~~

A Match is a particular instance of a game being played,
and holds the results of that instance, i.e. what the score was, who got paid what.

So, "Match" is used in the sense of "boxing match",
in the sense that it is an event that occurs where the game is played.

Example of a Match: "dictator game between users Alice & Bob, where Alice gave $0.50"

Implementation
______________

``Match`` classes should inherit from ``ptree.models.players.BaseMatch``. Here is the class structure:

.. py:class:: Match

    .. py:method:: is_ready_for_next_player(self)
    
        *You must implement this method yourself.*
        
        Whether the game is ready for another player to be added.
        
        If it's a non-sequential game (you do not have to wait for one player to finish before the next one joins),
        you can use this to assign players until the game is full::
        
            return not self.is_full()

    .. py:method:: is_full(self)
    
        Whether the match is full (i.e. no more Players can be assigned).
    
    .. py:method:: is_finished(self)
    
        Whether the match is completed.
        
    .. py:method:: players(self)
    
        Returns the ``Player`` objects in this match. 
        Syntactic sugar for ``self.player_set.all()``
        
        


Treatment
~~~~~~~~~

A Treatment is the definition of what everyone in the treatment group has to do.

Example of a treatment:
'dictator game with stakes of $1, where players have to chat with each other first'

A treatment is defined before the experiment starts.
Results of a game are not stored in ther Treatment object, they are stored in Match or Player objects.

Implementation
______________

``Treatment`` classes should inherit from ``ptree.models.players.BaseTreatment``. Here is the class structure:

.. py:class:: Treatment

    .. py:method:: sequence(self):
    
        *You must implement this method.*

        Very important. Returns a list of all the View classes that the user gets routed through sequentially.
        (Not all pages have to be displayed for all players; see the ``is_displayed()`` method)
        
        Example::
            
            import donation.views as views
            import ptree.views.concrete
            return [views.Start,
                    ptree.views.concrete.AssignPlayerAndMatch,
                    views.IntroPage,
                    views.EnterOfferEncrypted, 
                    views.ExplainRandomizationDetails, 
                    views.EnterDecryptionKey,
                    views.NotifyOfInvalidEncryptedDonation,
                    views.EnterOfferUnencrypted,
                    views.NotifyOfShred,
                    views.Survey,
                    views.RedemptionCode]

    .. py:attribute:: base_pay = models.PositiveIntegerField()
    
        How much each Player is getting paid to play the game
        
    .. py:attribute:: players_per_match
    
        Class attribute that specifies the number of players in each match. 
        For example, Prisoner's Dilemma has 2 players.
        a single-player game would just have 1.

    .. py:method:: matches(self):
    
            The matches in this treatment. Syntactic sugar for ``self.match_set.all()``


Experiment
~~~~~~~~~~
Coming soon. (You will not be using this object frequently.)
