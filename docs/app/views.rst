views.py
========

A View defines a single web page that is shown to participants. 
It is implemented as a Python class -- more specifically, a Django `class-based view <https://docs.djangoproject.com/en/dev/topics/class-based-views/generic-display/>`__.

If your experiment involves showing the participant a sequence of 5 pages,
your views.py will contain 5 View classes.

Here is what the code of a View should define (along with what attribute/method defines it):

- Whether a given participant sees this View (or whether it should be skipped): ``is_displayed()``
- What HTML template to display: ``template_name``
- What form to display on the page: ``form_class``
- What variables to insert into the template (for displaying dynamic content), and how to calculate those variables: ``get_template_variables``
- What to do after the participant has submitted a valid form: ``after_form_validates``

When a participant visits your site, they are routed through your views in the order you specify in :py:meth:`Treatment.sequence`.
The participant must submit a valid form before they get routed to the next page.
If the form they submit is invalid (e.g. missing or incorrect values),
it will be re-displayed to them along with the list of errors they need to correct.

Implementation
______________

Here is the structure of a class you would write:

.. py:class:: MyView(ptree.views.abstract.BaseView, ViewInThisApp)
    
    .. py:attribute:: participant
					  match
					  treatment
					  experiment
    
        The current participant, match, treatment, and experiment objects.
					
        These are provided for you automatically.
        However, you need to define the following attributes and methods:
		
		
    
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
            
    .. py:method:: get_template_variables(self)
    
        Get any variables that will be passed to the HTML template.
        Add them to the dictionary as key-value pairs.
        (You don't need to include the form; that will be handled automatically)
        
        Example::
        
            def get_template_variables(self):
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
        
        .. note::
        
            If your ``form_class`` inherits from ``ModelForm``, 
            then pTree will automatically save the submitted values to the database.
            But if you inherit from ``Form``,
            you will need to save the form fields to the database yourself here.
            (This is one of the advantages of using ``ModelForm``).
                
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

