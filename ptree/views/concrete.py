__doc__ = """This module contains views that are shared across many game types. 
They are ready to be included in your  Just import this module,
and include these classes in your Treatment's sequence() method."""

from ptree.views.abstract import (
    InitializeParticipantOrExperimenter,
    NonSequenceUrlMixin,
    PTreeMixin,
    ParticipantUpdateView,
    LoadClassesAndUserMixin,
)
import ptree.forms
from datetime import datetime
from django.shortcuts import get_object_or_404, render_to_response
from django.http import HttpResponse, HttpResponseRedirect
import vanilla
from django.utils.translation import ugettext as _
import ptree.constants as constants
import ptree.sessionlib.models
import ptree.common
import ptree.models.participants


class RedirectToPageUserShouldBeOn(NonSequenceUrlMixin, LoadClassesAndUserMixin, PTreeMixin, vanilla.View):
    name_in_url = 'shared'

    def get(self, request, *args, **kwargs):
        return self.redirect_to_page_the_user_should_be_on()

class OutOfRangeNotification(NonSequenceUrlMixin, PTreeMixin, vanilla.View):
    name_in_url = 'shared'

    def dispatch(self, request, *args, **kwargs):
        return HttpResponse('No more pages in this sequence.')

class WaitUntilAssignedToMatch(ParticipantUpdateView):
    """
    this is visited after Initialize, to make sure the participant has a match and treatment.
    the participant can be assigned at any time, but this is a safeguard,
    and therefore should be at the beginning of each subsession.
    Should it instead be called after InitializeSessionParticipant?
    Someday, we might want to shuffle participants dynamically,
    e.g. based on the results of the past game.
    """
    name_in_url = 'shared'

    def show_skip_wait(self):
        if self.match and self.treatment:
            return self.PageActions.skip
        return self.PageActions.wait

    def wait_page_body_text(self):
        return 'Waiting until participant is assigned to match and treatment.'

    def wait_page_response(self):
        """2/11/2014: same as parent method, but remove debug_values, which are not valid if the participant doesn't have
         a treatment assigned yet"""
        return render_to_response(
            self.wait_page_template_name,
            {
                'SequenceViewURL': self.wait_page_request_url(),
                'wait_page_body_text': self.wait_page_body_text(),
                'wait_page_title_text': self.wait_page_title_text()
            }
        )

class InitializeSessionExperimenter(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r'^InitializeSessionExperimenter/$'

    def get(self, *args, **kwargs):
        self.request.session.clear()
        self.request.session[constants.session_user_code] = self.request.GET[constants.session_user_code]
        return render_to_response('ptree/experimenter/StartSession.html', {})

    def post(self, request, *args, **kwargs):
        self.session_user = get_object_or_404(
            ptree.sessionlib.models.SessionExperimenter,
            code=self.request.session[constants.session_user_code]
        )

        # generate hash when the first participant starts, rather than when the session was created
        # (since code is often updated after session created)
        session = self.session_user.session
        if not session.git_hash:
            session.git_hash = ptree.common.git_hash()
            session.save()

        # assign participants to treatments
        for subsession in session.subsessions():
            subsession.assign_participants_to_treatments_and_matches()

        return HttpResponseRedirect(self.session_user.me_in_first_subsession.start_url())


class InitializeSessionParticipant(vanilla.UpdateView):

    @classmethod
    def url_pattern(cls):
        return r'^InitializeSessionParticipant/$'



    def get(self, *args, **kwargs):
        self.request.session.clear()

        # session code for mturk only? don't think there are any other scenarios currently.
        session_code = self.request.GET.get(constants.session_code)
        session_user_code = self.request.GET.get(constants.session_user_code)

        if not session_user_code or session_code:
            return HttpResponse('Missing parameter in URL')
        if session_user_code and session_code:
            return HttpResponse('Redundant parameters in URL')

        if session_user_code:
            session_user = get_object_or_404(ptree.sessionlib.models.SessionParticipant, code=session_user_code)
            session = session_user.session
        else:
            session = get_object_or_404(ptree.sessionlib.models.Session, )
            if session.is_for_mturk:
                try:
                    mturk_worker_id = self.request.GET[constants.mturk_worker_id]
                    mturk_assignment_id = self.request.GET[constants.mturk_assignment_id]
                    assert mturk_assignment_id != 'ASSIGNMENT_ID_NOT_AVAILABLE'
                except:
                    print 'A visitor to this subsession was turned away because they did not have the MTurk parameters in their URL.'
                    print 'This URL only works if clicked from a MTurk job posting with the JavaScript snippet embedded'
                    return HttpResponse(_('To participate, you need to first accept this Mechanical Turk HIT and then re-click the link (refreshing this page will not work).'))
                try:
                    session_user = ptree.sessionlib.models.SessionParticipant.objects.get(mturk_worker_id = mturk_worker_id,
                                                                      session = session)
                except self.ParticipantClass.DoesNotExist:
                    try:
                        session_user = ptree.sessionlib.models.SessionParticipant.objects.filter(session = session,
                                                                             visited=False)[0]
                    except IndexError:
                        raise IndexError("No Participant objects left in the database to assign to new visitor.")

                    session_user.mturk_worker_id = mturk_worker_id
                    session_user.mturk_assignment_id = mturk_assignment_id
            else:
                raise NotImplementedError()

        session_user.visited = True
        session_user.time_started = datetime.now()

        participant_label = self.request.GET.get(constants.session_participant_label)
        if participant_label is not None:
            session_user.label = participant_label

        if session_user.ip_address == None:
            session_user.ip_address = self.request.META['REMOTE_ADDR']

        session_user.save()

        self.request.session[constants.session_user_id] = session_user.id

        return HttpResponseRedirect(session_user.me_in_first_subsession.start_url())
