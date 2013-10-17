.. _forms:

forms.py
========

Each of your app's Views will display a form to the participant.

Even if the participant does not need to fill anything out,
they will usually at least see a button that takes them to the next page in their sequence.

ptree forms are based on Django `Forms <https://docs.djangoproject.com/en/dev/topics/forms/>`__
and `ModelForms <https://docs.djangoproject.com/en/dev/topics/forms/modelforms/#modelform>`__.

Your forms are defined in ``forms.py`` in your app.

.. py:class:: MyForm(ptree.forms.ModelForm)
    
    .. py:attribute:: participant
					  match
					  treatment
					  experiment
					  request
    
        The current participant, match, treatment, and experiment objects.
        Also, the HTTP request object.
        These are provided for you automatically.
        

    .. py:method:: get_initial_field_values
        
        Allows you to pre-fill form fields with initial/default values.
        Return a dictionary where the keys are field names and the values are the inital values of those fields in the form.
        One use case is during development/testing, to pre-fill fields to save yourself typing.
        For example, you might have a text transcription task that you don't want to fill out every time you test your app,
        so you could do this::
        
            def get_field_initial_values(self):
                if settings.DEBUG:
                    return {'transcription': 'Lorem ipsum dolor sit amet, consectetur adipiscing...'}
                else:
                    return {}
        
    .. py:method:: get_field_choices
        
        Lets you specify choices for a dropdown field.
        You can also set choices for a field in ``models.py`` using the ``choices`` argument,
        but those choices will be the same for everyone.
        Specifying choices here allows you to make the choices dynamic -- they can depend on 
        the current participant/match/treatment/request/etc.
        
        For dropdowns where users are choosing an amount of money, you can use this method
        in conjunction with ``make_field_currency_choices``, as follows::
        
            def get_field_choices(self):
                return {'amount_offered': self.make_field_currency_choices(self.treatment.offer_choices())}

        
	.. py:method:: customize(self)
	
		You can put any other code here to customize your fields.
		
	.. py:method:: make_field_currency_choices(self, field_name, amounts)
	
		This method will make an ``IntegerField`` (or ``FloatField``, etc.) 
		display as a dropdown menu with each amount displayed as a currency amounts.
		
		You need to call this in your form's ``initialize_form()`` method, like this::
		
			def initialize_form(self):
				# in this example, self.treatment.offer_choices() returns a list like [0, 10, 20, 30, 40, 50]
				self.make_field_currency_choices('amount_offered', self.treatment.offer_choices())
		

