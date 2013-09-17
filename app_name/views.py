from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse, Http404, HttpResponseRedirect

import {{ app_name }}.models
import ptree.views.abstract
import ptree.views.abstract
import ptree.views.concrete
import {{ app_name }}.forms

from django.conf import settings

class ViewInThisApp(object):
    """Keep this as is"""
    TreatmentClass = {{ app_name }}.models.Treatment
    MatchClass = {{ app_name }}.models.Match
    ParticipantClass = {{ app_name }}.models.Participant
    ExperimentClass = {{ app_name }}.models.Experiment
    
class Start(ptree.views.abstract.Start, ViewInThisApp):
    """Keep this as is"""

# change the name as necessary
class MyView(ViewInThisApp, ptree.views.abstract.PageWithModelForm):

    # substitute the 
    form_class = {{ app_name }}.forms.MyForm
    template_name = '{{ app_name }}/MyView.html'

    def is_displayed(self):
        pass

    def get_template_variables(self):
        return {}

    def after_form_validates(self, form):
        pass
        
# add more Views as you wish...        
