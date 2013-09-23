Creating your Django project
****************************

The first step is to create a Django project, which will contain your pTree experiments.
Instructions are `here <https://docs.djangoproject.com/en/dev/intro/tutorial01/#creating-a-project>`_.

When you run ``django-admin.py startproject <projectname>``, 
you can name your project anything you want, like ``ptree_experiments`` or ``experiments`` or ``games``.

.. note::

    To avoid confusion, don't call it ``ptree``, 
    because that name conflicts with the name of the pTree module you will be using.

In the section about configuring the database engine, follow the instructions for SQLite
(recommended for simplicity).

Follow the instructions up to and including the part about running ``python manage.py syncdb``.


settings.py
===========

In ``settings.py``, you should set the following values:

Find your ``INSTALLED_APPS``, add the following variables at the beginning, and uncomment ``'django.contrib.admin'``::

	INSTALLED_APPS = (
		'ptree',
		'data_exports',
		'crispy_forms',
		
		# Uncomment the next line to enable the admin:
		'django.contrib.admin',
		
		# rest of your apps...		
    )

After the definition of ``INSTALLED_APPS``, paste the following lines::

    PTREE_EXPERIMENT_APPS = ()
    INSTALLED_APPS += PTREE_EXPERIMENT_APPS

urls.py
=======

There is a line in ``urls.py`` to enable the admin site URL; uncomment it.

Add the following lines after the definition of ``urlpatterns``::

    import ptree.urls
    urlpatterns += ptree.urls.urlpatterns()

