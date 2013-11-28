from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.conf import settings
import extra_views
from ptree.forms import StubModelForm
from ptree.sequence_of_experiments.models import StubModel
import vanilla

import ptree.constants as constants

# import the logging library
import logging

logger = logging.getLogger(__name__)

REDIRECT_TO_PAGE_USER_SHOULD_BE_ON_URL = '/shared/RedirectToPageUserShouldBeOn/'

class ExperimenterMixin(object):
    @classmethod
    def get_url_base(cls):
        # look for url_base attribute on ExperimentClass
        # if it's not part of a game, but rather a shared module etc, ExperimentClass won't exist.
        # in that case, url_base needs to be defined on the class.
        return getattr(cls, 'ExperimentClass', cls).url_base

    @classmethod
    def url(cls):
        return '/{}/{}/'.format(cls.get_url_base(), cls.__name__)

    @classmethod
    def url_pattern(cls):
        return r'^{}/{}/$'.format(cls.get_url_base(), cls.__name__)


class ExperimenterSequenceMixin(ExperimenterMixin):
    class PageActions:
        show = 'show'
        skip = 'skip'
        wait = 'wait'

    def show_skip_wait(self):
        return self.PageActions.show

    wait_page_template = 'ptree/WaitPage.html'

    def wait_message(self):
        return None

    def get_success_url(self):
        return self.experiment.experimenter_sequence_as_urls()[self.request.session[constants.index_in_sequence_of_views]]

    def dispatch(self, request, *args, **kwargs):
        self.ExperimentClass = self.request.session[constants.ExperimentClass]
        self.experiment = self.ExperimentClass.objects.get(code = self.request.session[constants.experiment_code])

        ssw = self.show_skip_wait()

        # should also add GET parameter like check_if_prerequisite_is_satisfied, to be explicit.
        if self.request.is_ajax():
            no_more_wait = ssw != self.PageActions.wait
            return HttpResponse(int(no_more_wait))

        # if the participant shouldn't see this view, skip to the next
        if ssw == self.PageActions.skip:
            self.request.session[constants.index_in_sequence_of_views] += 1
            return HttpResponseRedirect(self.get_success_url())

        if ssw == self.PageActions.wait:
            return render_to_response(self.wait_page_template, {'SequenceViewURL': self.request.path,
                                                                'wait_message': self.wait_message()})
        return super(ExperimenterSequenceMixin, self).dispatch(request, *args, **kwargs)

    def variables_for_template(self):
        """
        Should be implemented by subclasses
        Return a dictionary that contains the template context variables (see Django documentation)
        You don't need to include the form here; that is taken care of automatically.
        """

        return {}

    def get_context_data(self, **kwargs):

        context = {}

        if kwargs.has_key(constants.form_invalid):
            context[constants.form_invalid] = True
            kwargs.pop(constants.form_invalid)

        context.update(super(ExperimenterSequenceMixin, self).get_context_data(**kwargs))
        context.update(self.variables_for_template())

        return context

    def get_form(self, data=None, files=None, **kwargs):
        kwargs.update({'experiment': self.experiment,
                       'request': self.request})

        cls = self.get_form_class()
        return cls(data=data, files=files, **kwargs)

    def after_valid_form_submission(self, form):
        """Should be implemented by subclasses as necessary"""
        pass

    def form_valid(self, form):
        self.after_valid_form_submission(form)
        self.request.session[constants.index_in_sequence_of_views] += 1
        return super(ExperimenterSequenceMixin, self).form_valid(form)

    def form_invalid(self, form):
        """

        """
        return self.render_to_response(self.get_context_data(form=form, form_invalid = True ))


class ExperimenterLaunch(ExperimenterMixin, vanilla.View):
    def get(self, request, *args, **kwargs):
        # clear all cookies, since they can cause problems if the participant has played a previous game.

        self.request.session.clear()

        experiment_code = self.request.GET[constants.experiment_code]
        experimenter_access_code = self.request.GET[constants.experimenter_access_code]

        experiment = get_object_or_404(self.ExperimentClass,
                          code = experiment_code,
                          experimenter_access_code = experimenter_access_code)

        self.request.session[constants.index_in_sequence_of_views] = 0
        self.request.session[constants.experiment_code] = experiment_code
        self.request.session[constants.ExperimentClass] = self.ExperimentClass
        return HttpResponseRedirect(experiment.experimenter_sequence_as_urls()[0])


class ExperimenterUpdateView(ExperimenterSequenceMixin, vanilla.UpdateView):
    form_class = StubModelForm

    def get_object(self):
        Cls = self.form_class.Meta.model
        if Cls == self.ExperimentClass:
            return self.experiment
        elif Cls == StubModel:
            return StubModel.objects.all()[0]


class ExperimenterCreateView(ExperimenterSequenceMixin, vanilla.CreateView):
    pass


class ExperimenterModelFormSetView(ExperimenterSequenceMixin, extra_views.ModelFormSetView):
    extra = 0

    def get_extra_form_kwargs(self):
        return {'experiment': self.experiment,
                'request': self.request}

    def after_valid_formset_submission(self, formset):
        for form in formset:
            self.after_valid_form_submission(form)

    def formset_valid(self, formset):
        self.after_valid_formset_submission(formset)
        self.request.session[constants.index_in_sequence_of_views] += 1
        return super(ExperimenterModelFormSetView, self).formset_valid(formset)
