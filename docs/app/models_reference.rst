pTree models reference
+++++++++++++++++++++++++++

When you create your pTree app from the template,
your models will be pre-defined for you.
They inherit  with the fields and methods in the below sections,
so you can just add whatever fields and methods you need for your particular experiment.

Participant
~~~~~~~~~~~

A ``Participant`` is a person who participates in a ``Match``.
For example, a Dictator Game match has 2 ``Participant`` objects.

A match can contain only 1 ``Participant`` if there is no interaction between ``Participant`` objects.
For example, a game that is simply a survey.

Implementation
______________


What is provided for you automatically
--------------------------------------

``Participant`` classes should inherit from ``ptree.models.participants.BaseParticipant``,
which gives you the following fields and methods:

match
=====

The ``Match`` this ``Participant`` is a part of.

index: PositiveIntegerField
============================

the ordinal position in which a participant joined a game. Starts at 0.

is_finished(self): boolean
===========================

whether the participant is finished playing (i.e. has seen the redemption code page).

What you must implement yourself
--------------------------------

bonus(self): integer
====================

The bonus the ``Participant`` gets paid, in addition to their base pay.

.. note::

	Add your own attributes or methods to this class.
   
Match
~~~~~

A Match is a particular instance of a game being played,
and holds the results of that instance, i.e. what the score was, who got paid what.

So, "Match" is used in the sense of "boxing match",
in the sense that it is an event that occurs where the game is played.

Example of a Match: "dictator game between participants Alice & Bob, where Alice gave $0.50"

Implementation
______________


What is provided for you automatically
--------------------------------------

``Match`` classes should inherit from ``ptree.models.participants.BaseMatch``,
which gives you the following fields and methods.

treatment
=========

The ``Treatment`` this ``Match`` is part of.

participants(self): list
========================

Returns the ``Participant`` objects in this match. 

is_full(self): boolean
======================
    
Whether the match is full, i.e.::

	return len(self.participants()) >= self.treatment.participants_per_match

is_finished(self): boolean
==========================

Whether the match is completed (i.e. ``is_finished()`` is ``True`` for each participant).	
	
What you must implement yourself
--------------------------------

is_ready_for_next_participant(self): boolean
============================================

Whether the game is ready for another participant to be added.

If it's a non-sequential game (you do not have to wait for one participant to finish before the next one joins),
you can use this to assign participants until the game is full::

	return not self.is_full()

Treatment
~~~~~~~~~

A Treatment is the definition of what everyone in the treatment group has to do.

Example of a treatment:
'dictator game with stakes of $1, where participants have to chat with each other first'

A treatment is defined before the experiment starts.
Results of a game are not stored in Treatment object, they are stored in Match or Participant objects.

Implementation
______________

What is provided for you automatically
--------------------------------------

``Treatment`` classes should inherit from ``ptree.models.participants.BaseTreatment``,
which gives you the following fields and methods.

matches(self): list
===================
    
The ``Match`` objects in this ``Treatment``.

base_pay: PositiveIntegerField
==============================
    
How much each Participant is getting paid to play the game.
Needs to be set when you instantiate your ``Participant`` objects.

What you must implement yourself
--------------------------------

sequence(self): list
====================
    
Very important. Returns a list of all the View classes that the participant gets routed through sequentially.
(Not all pages have to be displayed for all participants; see the ``is_displayed()`` method).
Must start with your app's ``StartTreatment``, and usually ends the Redemption Code view.
The rest is up to you.

Inside the method, you should import the modules containing the views you want to use.

Example::
	
	import donation.views as views
	import ptree.views.concrete
	return [views.StartTreatment,
			ptree.views.concrete.AssignParticipantAndMatch,
			views.IntroPage,
			views.EnterOfferEncrypted, 
			views.ExplainRandomizationDetails, 
			views.EnterDecryptionKey,
			views.NotifyOfInvalidEncryptedDonation,
			views.EnterOfferUnencrypted,
			views.NotifyOfShred,
			views.Survey,
			ptree.views.concrete.RedemptionCode]
        
participants_per_match: int
============================

Class attribute that specifies the number of participants in each match. 
For example, Prisoner's Dilemma has 2 participants.
a single-participant game would just have 1.


Experiment
~~~~~~~~~~
An experiment is generally a randomization between treatments, though it could just have one treatment.

Most experiments won't need to access the experiment class, but info is provided here for the sake of completeness.

Implementation
______________


What is provided for you automatically
--------------------------------------

treatments(self): list
======================

Returns the ``Treatment`` objects in this ``Experiment``. 

Methods that are optional to define
-----------------------------------

pick_treatment_for_incoming_participant(self): Treatment
=========================================================

This method will get called when a participant arrives at your site,
and needs to be randomized to a treatment.
Unless you override it,
this method returns a random choice between the treatments in the experiment,
weighted by their ``randomization_weight``::

    def pick_treatment_for_incoming_participant(self):
        choices = [(treatment, treatment.randomization_weight) for treatment in self.treatment_set.all()]
        treatment = self.weighted_randomization_choice(choices)
        return treatment

