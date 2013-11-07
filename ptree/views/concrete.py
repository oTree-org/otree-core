__doc__ = """This module contains views that are shared across many game types. 
They are ready to be included in your  Just import this module,
and include these classes in your Treatment's sequence() method."""


from django.shortcuts import render_to_response

from django.conf import settings

import ptree.views.abstract
import ptree.forms

class ViewInThisApp(object):
    url_base = 'shared'

class RedirectToPageUserShouldBeOn(ptree.views.abstract.View, ViewInThisApp):
    def get(self, request, *args, **kwargs):
        return self.redirect_to_page_the_user_should_be_on()

class RedemptionCode(ptree.views.abstract.SequenceView, ptree.views.abstract.TemplateView, ViewInThisApp):

    def variables_for_template(self):

        return {'redemption_code': self.participant.code,
                'base_pay': self.treatment.base_pay,
                'bonus': self.participant.bonus(),
                'total_pay': self.participant.total_pay()}