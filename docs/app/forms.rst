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
        

	.. py:method:: customize(self)
	
		You can put any code here to customize how fields get displayed.
		
	.. py:method:: make_field_currency_choices(self, field_name, amounts)
	
		This method will make an ``IntegerField`` (or ``FloatField``, etc.) 
		display as a dropdown menu with each amount displayed as a currency amounts.
		
		You need to call this in your form's ``initialize_form()`` method, like this::
		
			def initialize_form(self):
				# in this example, self.treatment.offer_choices() returns a list like [0, 10, 20, 30, 40, 50]
				self.make_field_currency_choices('amount_offered', self.treatment.offer_choices())
		

