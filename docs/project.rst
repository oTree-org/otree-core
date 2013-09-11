Creating your Django project
****************************

Your pTree experiments will be contained inside a Django project.
The first step is to create a Django project.
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

``INSTALLED_APPS``: add ``'ptree'`` near the top, followed by ``'django.contrib.admin'``.
Also add ``'crispy_forms'``.

After the definition of ``INSTALLED_APPS``, paste the following lines::

    PTREE_EXPERIMENT_APPS = []
    INSTALLED_APPS += PTREE_EXPERIMENT_APPS

urls.py
=======

There is a line in ``urls.py`` to enable the admin site URL; uncomment it.

Add the following lines after the definition of ``urlpatterns``::

    import ptree.urls
    urlpatterns += ptree.urls.urlpatterns()

