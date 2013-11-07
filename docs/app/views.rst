views.py
========

A View defines a single web page that is shown to participants. 
It is implemented as a Python class -- more specifically, a Django `class-based view <https://docs.djangoproject.com/en/dev/topics/class-based-views/generic-display/>`__.

For example, if your experiment involves showing the participant a sequence of 5 pages,
your views.py should contain 5 View classes.

When a participant visits your site, they are routed through your views in the order you specify in your treatment's ``sequence_of_views()`` method.

The participant must submit a valid form before they get routed to the next page.
If the form they submit is invalid (e.g. missing or incorrect values),
it will be re-displayed to them along with the list of errors they need to correct.

Here is what the code of a View should define (along with what attribute/method defines it):

In your view code, ptree automatically provides you with attributes called
``participant``, ``match``, ``treatment``, and ``experiment``,
so that you can access the current participant, match, treatment, and experiment objects,
and get/set fields or call those objects' methods.

UpdateView
++++++++++++

Most of the time, your view class will inhert from ``ptree.views.UpdateView``.

Attributes
______________

Provided for you
.................

participant
------------

The current participant.

match
------

The current match.

treatment
----------

The current treatment.

experiment
-----------

The current experiment.


Required
..........

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

Provided for you
..................    
    
time_limit_was_exceeded: boolean
---------------------------------

Only available on POST (i.e., after the user submits the form).
Indicates whether the participant exceeded the time limit specified in ``time_limit_seconds()``.
    
Methods
________    
    
Optional
.........    

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


show_skip_wait()
-----------------

Whether this view should be shown, skipped, or whether the participant has to wait.
Default behavior is to show the page.

In the case where the participant has to wait, he is redirected to a waiting page
that will make an AJAX call to this method every N seconds.
The participant will have to wait until this method returns Show or Skip.

Example::

    def show_skip_wait(self):
        if self.participant.open_envelope is None:
            return self.PageActions.wait
        return self.PageActions.show
    
wait_message()
-------------------

The message to display to users on the waiting page.
(See ``show_skip_wait()``).

after_valid_form_submission()
----------------------------------------

After the participant submits the form,
ptree makes sure that it has all the required values
(and re-displays to the participant with errors otherwise).

Here you can put anything additional that should happen after the form validates.
If you don't need anything to be done, it's OK to leave this method blank,
or to leave it out entirely.

time_limit_seconds()
---------------------

Your page can have a time limit, in which case the participant will see a countdown timer on the page.
This method lets you define what that time limit is.
If the user exceeds the time limit, they can still submit the form, but once they submit,
the ``time_limit_was_exceeded`` attribute will be set to ``True``, which you can use to do anything you want.
    

StartTreatment
+++++++++++++++
    
Every app needs to define a ``StartTreatment`` view that inherits from ``ptree.views.StartTreatment``.
This view displays a welcome page to users,
followed by a "Next" button if they wish to start.
This page gives users a chance to drop out *before* we assign them to a match, 
thus preventing "orphan" matches.
Behind the scenes, this view also plays an important role in initializing the database session.

RedemptionCode
++++++++++++++++

Should inherit from ``ptree.views.RedemptionCode``.

This view should usually be the last View in your sequence.
It tells the user how much they made,
and also gives them their redemption code.

CreateView, TemplateView, SequenceTemplateView, CreateMultipleView, UpdateMultipleView
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

Under development.