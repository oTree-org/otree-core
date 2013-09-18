Writing a pTree app
*******************

Creating the app
================

First, choose a name for your app that is descriptive and short,
since you will be typing it and using it frequently.
For example, if you are implementing the `prisoner's dilemma <http://en.wikipedia.org/wiki/Prisoner's_dilemma>`__,
you can choose the name ``prisoner``.
If you are implementing the `public goods game <http://en.wikipedia.org/wiki/Public_goods_game>`_,
you can choose the name ``publicgoods``.

At your command line, run this command, where <app_name> is the name you have chosen for your app::

    django-admin.py startapp --template https://github.com/wickens/django-ptree/releases/download/latest/app_template.zip <app_name>
    
.. note::

    This will create a new app based on a pTree template, with most of the structure already set up for you.

    
Once your app has been created,
go to ``settings.py`` and append its name (as a string) to ``PTREE_EXPERIMENT_APPS``, like this::
    
    PTREE_EXPERIMENT_APPS = ('myappname',)

Writing the code    
================

The directory structure of your new app will look like this::

    management/
    static/
    templates/
    admin.py
    forms.py
    models.py
    views.py
    
Each of these files/folders holds one component of your app. They are explained in the following pages:    

.. toctree::
   :maxdepth: 2
   
   models
   forms
   views
   templates
   management
   admin