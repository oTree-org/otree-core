models.py
*******************

Introduction to models
++++++++++++++++++++++

The purpose of running an experiment is to record data --
what treatments are in your experiment,
what games were played in those treatments,
what the results were,
what actions the participants took, etc.

pTree stores your data in database tables (SQL).
For example, let's say you are programming an ultimatum game,
where in each 2-person match, one participant makes a monetary offer (say, 0-100 cents),
and another participant either rejects or accepts the offer.
You will want your "Match" table to look something like this:

    +----------+----------------+----------------+ 
    | Match ID | Amount offered | Offer accepted |
    +==========+================+================+
    | 1        | 50             | TRUE           |
    +----------+----------------+----------------+ 
    | 2        | 25             | FALSE          |
    +----------+----------------+----------------+ 
    | 3        | 50             | TRUE           |
    +----------+----------------+----------------+ 
    | 4        | 0              | FALSE          |
    +----------+----------------+----------------+ 
    | 5        | 60             | TRUE           |
    +----------+----------------+----------------+ 

In order to end up with a table like this this, you need to define a Django model,
which is a Python class that defines a database table.
You define what fields (columns) are in the table,
what their data types are, and so on.
When you run your experiment, the SQL tables will get automatically generated,
and each time users visit, new rows will get added to the tables.

Here is what the model might look like for the above "Match" table::

    class Match(ptree.models.BaseModel):
        amount_offered = models.IntegerField()
        offer_accepted = models.BooleanField()
    
This class will be placed in your app's ``models.py`` file.

Every pTree app needs the following 4 models:

- Participant
- Match
- Treatment
- Experiment

They are related to each other as follows:

A ``Participant`` is part of a ``Match``, which is part of a ``Treatment``, which is part of an ``Experiment``.

Furthermore, there are usually multiple ``Participant`` objects in a ``Match``, 
multiple ``Match`` objects in a ``Treatment``, 
and multiple ``Treatment`` objects in an ``Experiment``, meaning that your objects would look something like this:

.. image:: model-hierarchy.png

How to define a model
+++++++++++++++++++++

pTree models are Django models with some extra fields and capabilities.
To be able to define a model, 
you need to read the Django documentation on models and understand:

- Different types of model fields. The full list is `here <https://docs.djangoproject.com/en/dev/ref/models/fields/#model-field-types>`__. You don't have to know all field types. Just make sure you at least know ``IntegerField``, ``PositiveIntegerField``, ``CharField``, ``BooleanField``, ``NullBooleanField``, and ``FloatField``.
- Field options (explained `here <https://docs.djangoproject.com/en/dev/topics/db/models/#field-options>`__).
- Verbose field names (explained `here <https://docs.djangoproject.com/en/dev/topics/db/models/#verbose-field-names>`__).
- Model methods (explained `here <https://docs.djangoproject.com/en/dev/topics/db/models/#model-methods>`__).