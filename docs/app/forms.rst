.. _forms:

forms.py
========

Most of your app's Views will display a form to the participant.

Even if the participant does not need to fill anything out,
they will usually at least see a button that takes them to the next page in their sequence.

ptree forms are based on Django `Forms <https://docs.djangoproject.com/en/dev/topics/forms/>`__
and `ModelForms <https://docs.djangoproject.com/en/dev/topics/forms/modelforms/#modelform>`__.

Your forms are defined in ``forms.py`` in your app, and should inherit from ``ptree.forms.ModelForm``.


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

request
--------

The HTTP request object (documented `here <https://docs.djangoproject.com/en/dev/ref/request-response/#httprequest-objects>`__).


field_initial_values()
----------------------

Allows you to pre-fill form fields with initial/default values.
Return a dictionary where the keys are field names and the values are the inital values of those fields in the form.
One use case is during development/testing, to pre-fill fields to save yourself typing.
For example, you might have a text transcription task that you don't want to fill out every time you test your app,
so you could do this::

    def field_initial_values(self):
        if settings.DEBUG:
            return {'transcription': 'Lorem ipsum dolor sit amet, consectetur adipiscing...'}
        else:
            return {}

field_choices()
----------------

Lets you specify choices for a dropdown field.
Return a dictionary in the same format as ``field_initial_values``.
You can also set choices for a field in ``models.py`` using the ``choices`` argument,
but those choices will be the same for everyone.
Specifying choices here allows you to make the choices dynamic -- they can depend on 
the current participant/match/treatment/request/etc.

For dropdowns where users are choosing an amount of money, you can use this method
in conjunction with ``currency_choices``, as follows::

    def field_choices(self):
        return {'amount_offered': self.currency_choices([0, 10, 20, 30, 40])}

field_labels()
---------------        

Specify the labels of the fields.
Return a dictionary in the same format as ``field_initial_values``.

Example::

    def field_labels(self):
        return {'amount_returned': 
                'If given {} (which gets multiplied into {}), I want to send back:'.format(self.instance.amount_offered,
                                                                                           self.instance.amount_offered_after_multiplying())}

currency_choices(amounts)
---------------------------------------------------------

This method will make an ``IntegerField`` (or ``FloatField``, etc.) 
display as a dropdown menu with each amount displayed as a currency amounts.

You will typically want to use this in your form's ``field_choices()`` method.

