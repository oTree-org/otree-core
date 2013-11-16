Auxiliary models
*******************

As discussed earlier, the 4 core models in this diagram:

.. image:: model-hierarchy.png

ptree provides you with a fifth type of model, ``AuxiliaryModel``, 
that you can use to store data that doesn't fit well on any of the above models.

Reasons for using an auxiliary model include:

- You want a model that can be reused in any app,
like a standard questionnaire or qualification test.

- Your match or participant needs to store the same type of information multiple times.
For example, in a 2-participant match where Participant 1 makes an offer and Participant 2 responds,
and there are multiple rounds of this process, your fields may look like this::
    
    class Match(...):
        
        offer_1 = models.IntegerField()
        response_1 = models.BooleanField()

        offer_2 = models.IntegerField()
        response_2 = models.BooleanField()

        offer_3 = models.IntegerField()
        response_3 = models.BooleanField()
        
        ...
    
This is a sign that you could make your code more concise and robust with an auxiliary model.
In models.py, add this::

    class Round(ptree.models.AuxiliaryModel):
        offer = models.IntegerField()
        response = models.BooleanField()
    
In forms.py, add this:

    class OfferForm(ptree.forms.ModelForm):
        class Meta:
            model = myapp.models.Round
            fields = ['offer']

    class ResponseForm(ptree.forms.ModelForm):
        class Meta:
            model = myapp.models.Round
            fields = ['response']
                        
In views.py, create a view. In this case, ``OfferView`` should inherit form ``ptree.views.CreateView``,
rather than ``ptree.views.UpdateView``, since we are creating a ``Round`` object from scratch,
rather than updating an existing ``Round``. After a valid form submission, a new ``Round`` object will be created.
and associated by a ``ForeignKey`` to the ``Participant`` who created it (as well as the current ``Match``)::

    class OfferView(ViewInThisApp, ptree.views.CreateView):

        template_name = 'myapp/Offer.html'
        form_class = myapp.forms.OfferForm

Then, for Participant 2, you can retrieve the ``Round`` in an UpdateView
by adding a ``get_object`` method::
        
    class ResponseView(ViewInThisApp, ptree.views.UpdateView):

        template_name = 'myapp/Response.html'
        form_class = myapp.forms.ResponseForm
        
        def get_object(self):
            return OfferAndResponse.objects.get(match=self.match)

Now you can put ``OfferView`` and ``ResponseView`` into your treatment's ``sequence()`` method
multiple times in a row, to create multiple ``Round`` objects in your database.