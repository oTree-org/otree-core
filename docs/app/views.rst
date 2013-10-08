views.py
========

A View defines a single web page that is shown to participants. 
It is implemented as a Python class -- more specifically, a Django `class-based view <https://docs.djangoproject.com/en/dev/topics/class-based-views/generic-display/>`__.

For example, if your experiment involves showing the participant a sequence of 5 pages,
your views.py should contain 5 View classes.

When a participant visits your site, they are routed through your views in the order you specify in :py:meth:`Treatment.sequence`.

The participant must submit a valid form before they get routed to the next page.
If the form they submit is invalid (e.g. missing or incorrect values),
it will be re-displayed to them along with the list of errors they need to correct.

Here is what the code of a View should define (along with what attribute/method defines it):

- Whether a given participant sees this View (or whether it should be skipped): ``is_displayed()``
- What HTML template to display: ``template_name``
- What form to display on the page: ``form_class``
- What variables to insert into the template (for displaying dynamic content), and how to calculate those variables: ``get_variables_for_template``
- What to do after the participant has submitted a valid form: ``after_form_validates``

In your view code, pTree automatically provides you with attributes called
``participant``, ``match``, ``treatment``, and ``experiment``,
so that you can access the current participant, match, treatment, and experiment objects,
and get/set fields or call those objects' methods.

Implementation
______________

Here is the structure of a class you would write:

.. py:class:: MyView(ptree.views.abstract.StandardView, ViewInThisApp)
        
    .. py:attribute:: template_name
    
        The name of the HTML template to display.
        
        Example::
        
            # This will look inside your app under the 'templates' directory, to '/app_name/MyView.html'
            template_name = 'app_name/MyView.html'
            
            # This will use the pTree built-in 'Start' template
            template_name = 'ptree/Start.html'
    
    .. py:attribute:: form_class
    
        The form to display on this page.
        Usually this will be the name of a form class defined in your ``forms.py``.
        (See :ref:`forms` for more info.)

        Example::

            form_class = app_name.forms.MyForm
        
    .. py:method:: is_displayed(self)
    
        Whether a given participant sees this View (or whether it should be skipped).
        If you don't define this method, all participants in the treatment will see this page.
        
        Example::
        
            def is_displayed(self):
                """only display this page to participants who made an offer of 0"""
                return self.participant.offer == 0
            
    .. py:method:: get_variables_for_template(self)
    
        Get any variables that will be passed to the HTML template.
        Add them to the dictionary as key-value pairs.
        (You don't need to include the form; that will be handled automatically)
        
        Example::
        
            def get_variables_for_template(self):
                return {'CHARITY': CHARITY,
                    'is_hypothetical': self.treatment.probability_of_honoring_split_as_fraction() == 0,
                    'max_offer_amount': self.treatment.max_offer_amount,
                    'participant_gets_all_money_if_no_honor_split': self.treatment.participant_gets_all_money_if_no_honor_split}
        

    
    .. py:method:: after_form_validates(self, form) 
    
        After the participant submits the form,
        pTree makes sure that it has all the required values
        (and re-displays to the participant with errors otherwise).
        
        Here you can put anything additional that should happen after the form validates.
        If you don't need anything to be done, it's OK to leave this method blank,
        or to leave it out entirely.

        You can access form fields like this::
        
            password = form.cleaned_data['password']
            
        Example::
        
            def after_form_validates(self, form):
                if self.treatment.probability_of_honoring_split_as_fraction() == 1:
                
                    # note: you can access form data through the form.cleaned_data dictionary,
                    # as defined here: https://docs.djangoproject.com/en/dev/ref/forms/api/#accessing-clean-data
                    self.match.amount_given = form.cleaned_data['amount_offered']
                    self.match.split_was_honored = True
                elif self.treatment.probability_of_honoring_split_as_fraction() == 0:
                    self.match.amount_given = self.treatment.amount_given_if_no_honor_split()
                    self.match.split_was_honored = False

                                        
Built-in views
______________

pTree provides some commonly used views.

.. py:class:: Start
    
Every app needs to define a ``Start`` view that inherits from ``ptree.views.abstract.Start``.
This view displays a welcome page to users and an overview of the task they will be performing,
followed by a "Next" button.
This page gives users a chance to drop out *before* we assign them to a match, 
thus preventing "orphan" games.
Behind the scenes, this view also plays an important role in initializing the database session.

If you'd like to display different text on the page,
or have a start form with fields other than ``nickname``,
you can just override the ``form_class`` or ``template_name``.

.. py:class:: ptree.views.concrete.RedemptionCode

This view should usually be the last View in your sequence.
It tells the user how much they made,
and also gives them their redemption code.

The template is in your project's ``ptree/templates/ptree/RedemptionCode.html``.
You can have a look at the various blocks in that template to see how you can customize it.

Out-of-sequence views
__________________

Sometimes you will want to have a view that is not in the sequence.
For example, let's say you want a link that opens in a new page and displays some information, 
but has no form for the user to fill out.

To do this, define a View that inherits from ``ptree.views.abstract.TemplateView`` rather than ``ptree.views.abstract.StandardView``.
define ``template_name`` and ``get_variables_for_template``, but none of the other methods and attributes.

Real-time interaction
_____________________

You may want your game to involve some real-time interaction between participants, or with the experiment administrator.
For example, let's say you build a 4-participant game where all 4 participants must complete some action before anyone can proceed to the next view.

In this case, you will need to display a "please wait" page to participants,
and only display the "Next" button when the condition is met.

This kind of functionality can be built with a common technique called AJAX.
The below code demonstrates this.

First, you need to write the HTML div that is displayed while the participant is waiting,
like this Bootstrap progress bar::

    <div class="progress progress-striped active" id='waitingIndicator'>
      <div class="progress-bar"  role="progressbar" style="width: 100%">
        <span class="sr-only">Please wait</span>
      </div>
    </div>

Then below it write the HTML div that is displayed when the user is ready for the next step.
This could be the page's form (which contains the "Next" button)::
    
    <div id='goToNextPage' style='display:none'>
        {% include "Form.html" %}
    </div>

Note the ``style='display:none'``, which gives that div an initial hidden state.
    
Now, you need to write the JavaScript/jQuery code that queries your server at regular intervals,
and when it gets the desired response from the server, toggles the visibility of the divs::

    <script type="text/javascript">
    var checkIfReady = function() {

        var args = { type: "GET", url: "{{ checkIfReadyURL }}", complete: addNextButtonIfReady };
        $.ajax(args);

    }

    var addNextButtonIfReady = function(res, status) {
        if (status == "success") {
            var response = res.responseText;
            if (response == "1") {
                $('#goToNextPage').show();
                $('#waitingIndicator').hide();
                
                window.clearInterval(intervalId);
            }
        }
    }

    var SECOND = 1000;
    var intervalId = window.setInterval("checkIfReady()", 20 * SECOND);
    </script>

Now we need to write the Python code on the server that will process these JavaScript requests.
This will be a View, but instead of inheriting from ``StandardView``, it should inherit from ``BaseView``,
and should define a ``get`` method that responds to HTTP ``GET`` requests.
In this example, it returns a boolean (1 or 0)::

    class CheckIfReady(BaseView):

        def get(self, request, *args, **kwargs):
            
            # Let's imagine some method exists in your Match class called "all_participants_are_ready".
            if self.match.all_participants_are_ready()
                return HttpResponse('1')
            else:
                return HttpResponse('0')

The final step is to connect the JavaScript code to the Python code.
We do this by passing the URL of the CheckIsReady view as a template variable::

    def get_variables_for_template(self):
        return { 'checkIfReadyURL': CheckIfReady.url(),
                 # other template variables go here... }
               
In our JavaScript above, this variable is inserted in the AJAX request as ``url: "{{ checkIfReadyURL }}"``,
so the AJAX requests will be handled by the Python view you defined.
        
                
Questionnaires
_______________

Frequently, you will want users to fill out a questionnaire/survey,
in addition to taking part in your experiment/game.
You can use pTree to create a survey,
but a potentially more efficient approach is to embed or link to a survey
from a service like SurveyGizmo, SurveyMonkey, WuFoo, Qualtrics, or Google Forms.
These services all have easy-to-use visual interfaces for creating and analyzing data from surveys.
With some of these services, you can embed a survey on your site so that it looks like it's part of pTree.
You can see an example of this in the template ``ptree/SurveyGizmoEmbedded.html``.
Just make sure to pass the participant's identifier to the survey
so that you can link the survey to that participant later.