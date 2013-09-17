"""Documentation at http://django-ptree.readthedocs.org/en/latest/app.html"""

from django.db import models

import ptree.models.matches
import ptree.models.players
import ptree.models.treatments
import ptree.models.experiments

from django.conf import settings

class Experiment(ptree.models.experiments.BaseExperiment):

    # this will be in the URL users see,
    # so you may want to change it to a code name
    # if you don't want to reveal to users the name of the experiment.
    url_base = '{{ app_name }}'

    
class Treatment(ptree.models.treatments.BaseTreatment):
    experiment = models.ForeignKey(Experiment)
    
    players_per_match = 1
    
    # define any other attributes or methods here.
    
    def sequence(self):
    
        import {{ app_name }}.views
        import ptree.views.concrete
        
        return [{{ app_name }}.views.Start,
                ptree.views.concrete.AssignPlayerAndMatch,
                {{ app_name }}.views.MyView, # insert your views here
                ptree.views.concrete.RedemptionCode]
                
class Match(ptree.models.matches.BaseMatch):
    
    treatment = models.ForeignKey(Treatment)
    
    # define any other attributes or methods here.
    
    def is_ready_for_next_player(self):
        """You must implement this yourself"""
            
class Player(ptree.models.players.BasePlayer):
    experiment = models.ForeignKey(Experiment)
    match = models.ForeignKey(Match, null = True)
    
    # define any other attributes or methods here.
    
    def bonus(self):
        """
        You must implement this yourself.
        """
            
    
    

