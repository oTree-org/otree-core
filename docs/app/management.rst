.. _management:

Populating the database
***********************

Before you launch your experiments,
you need to populate your database with Experiment, Treatment, and Match objects.

Which objects to create
=======================

Experiment
	Create the experiment that contains your treatments.

Treatments
	Your experiment will likely involve several treatments,
	each with its own parameters, payoffs, etc.

Participants
	You should actually create empty Participant objects before anyone visits your site.
	For each participant, a single-use URL is created.
	You will give each URL to a single participant in your experiment.
	With single-use URLs, you can control how many people take part in your experiment,
	and prevent the same person from playing twice.
	
.. note::

	You do not need to create Match objects in advance.
	Match objects are created on the fly when participants visit the site.
	This allows ptree to randomize Matches to Treatments,
	regardless of the order in which participants visit the site.

How to create your objects
===========================

In your app, under ``management/commands``,
open ``[app_name]_create_objects.py``.
and edit the function ``create_objects``.
In particular, you may want to customize the parameters of your Treatments,
as well as the numbers of Treatments and Participants. 

Then, whenever you launch your site (either for testing or the live version of the site), 
you will be able to create your objects by running the following command from your command line::

	python manage.py [your_app_name]_create_objects

You can then browse the newly created objects in the ptree Experimenter Console,
as explained in :ref:`admin`.