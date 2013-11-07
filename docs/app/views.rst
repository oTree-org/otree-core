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

- Whether a given participant sees this View (or whether it should be skipped): ``show_skip_wait()``
- What HTML template to display: ``template_name``
- What form to display on the page: ``form_class``
- What variables to insert into the template (for displaying dynamic content), and how to calculate those variables: ``variables_for_template``
- What to do after the participant has submitted a valid form: ``after_valid_form_submission``

In your view code, ptree automatically provides you with attributes called
``participant``, ``match``, ``treatment``, and ``experiment``,
so that you can access the current participant, match, treatment, and experiment objects,
and get/set fields or call those objects' methods.

Attributes
______________

template_name
--------------

The name of the HTML template to display.

Example::

    # This will look inside your app under the 'templates' directory, to '/app_name/MyView.html'
    template_name = 'app_name/MyView.html'
    
    # This will use the ptree built-in 'Start' template
    template_name = 'ptree/Start.html'

form_class
-----------

The form to display on this page.
Usually this will be the name of a form class defined in your ``forms.py``.
(See :ref:`forms` for more info.)

Example::

    form_class = app_name.forms.MyForm

time_limit_was_exceeded: boolean
---------------------------------

Only available on POST (i.e., after the user submits the form).
Indicates whether the participant exceeded the time limit specified in ``time_limit_seconds()``.
    
    
Methods
________    
    
show_skip_wait()
-----------------

Whether this view should be shown, skipped, or whether the participant has to wait.
In the case where the participant has to wait, he is redirected to a waiting page
that will make an AJAX call to this method every N seconds.
The participant will have to wait until this method returns Show or Skip.
Default behavior is to show the page.

Example::

    def show_skip_wait(self):
        if self.participant.open_envelope is None:
            return self.PageActions.wait
        return self.PageActions.show
    
wait_message()
-------------------

The message to display to users on the waiting page.
(See ``show_skip_wait()``).

time_limit_seconds()
---------------------

Your page can have a time limit, in which case the participant will see a countdown timer on the page.
This method lets you define what that time limit is.
If the user exceeds the time limit, they can still submit the form, but once they submit,
the ``time_limit_was_exceeded`` attribute will be set to ``True``, which you can use to do anything you want.


variables_for_template()
--------------------------

Get any variables that will be passed to the HTML template.
Add them to the dictionary as key-value pairs.
(You don't need to include the form; that will be handled automatically)

Example::

    def variables_for_template(self):
        return {'CHARITY': CHARITY,
                'is_hypothetical': self.treatment.probability_of_honoring_split_as_fraction() == 0,
                'max_offer_amount': self.treatment.max_offer_amount,
                'participant_gets_all_money_if_no_honor_split': self.treatment.participant_gets_all_money_if_no_honor_split}

after_valid_form_submission()
----------------------------------------

After the participant submits the form,
ptree makes sure that it has all the required values
(and re-displays to the participant with errors otherwise).

Here you can put anything additional that should happen after the form validates.
If you don't need anything to be done, it's OK to leave this method blank,
or to leave it out entirely.


CreateView
___________

See the page on AuxiliaryModels.

TemplateView
______________________

Sometimes you will want to have a view that is not in the sequence.
For example, let's say you want a link that opens in a new page and displays some information, 
but has no form for the user to fill out.

To do this, define a View that inherits from ``ptree.views.TemplateView`` rather than ``ptree.views.abstract.UpdateView``.
define ``template_name`` and ``variables_for_template``, but none of the other methods and attributes.

AjaxView
__________

Any view that should handle AJAX calls.
You should implement your own ``get`` and/or ``post`` methods.

e.g.::

    def get(self, request):
        ...
        
    def post(self, request):
        ...
    
Built-in views
______________

ptree provides some commonly used views.

Start
------
    
Every app needs to define a ``Start`` view that inherits from ``ptree.views.abstract.Start``.
This view displays a welcome page to users,
followed by a "Next" button if they wish to start.
This page gives users a chance to drop out *before* we assign them to a match, 
thus preventing "orphan" matches.
Behind the scenes, this view also plays an important role in initializing the database session.

If you'd like to display different text on the page,
or have a start form with fields other than ``nickname``,
you can just override the ``form_class`` or ``template_name``.

RedemptionCode
---------------

This view should usually be the last View in your sequence.
It tells the user how much they made,
and also gives them their redemption code.

