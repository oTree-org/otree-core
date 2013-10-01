Setting up your Django project
******************************

pTree is built on top of Django, 
which is the most popular web development framework for Python.
When you install pTree, Django will get installed automatically.

Create your project
===================

From the command line, ``cd`` into a directory where you'd like to store your
code (can be anywhere, like a folder in "My Documents" or "Documents"), 
then run the following command::

   django-admin.py startproject ptree_experiments

This will create a ``ptree_experiments`` directory in your current directory. If it didn't
work, see the `troubleshooting <https://docs.djangoproject.com/en/dev/faq/troubleshooting/#troubleshooting-django-admin-py>`__ page.
	
Test that it worked
-------------------

Let's verify this worked. Change into the outer :file:`ptree_experiments` directory, if
you haven't already, and run the command ``python manage.py runserver``. You'll
see the following output on the command line::

    Validating models...

    0 errors found
    |today| - 15:50:53
    Django version |version|, using settings 'ptree_experiments.settings'
    Starting development server at http://127.0.0.1:8000/
    Quit the server with CONTROL-C.

Now that the server's running, visit http://127.0.0.1:8000/ with your Web
browser. You'll see a "Welcome to Django" page, in pleasant, light-blue pastel.
It worked!

Configure your project
======================

Launch PyCharm, and select "Open Directory".
Navigate to the outer ``ptree_experiments`` directory and click OK.
When the project opens, on the left-hand site you should see a directory tree that expands to the following::

    ptree_experiments/
        manage.py
        ptree_experiments/
            __init__.py
            settings.py
            urls.py
            wsgi.py

Edit the following files.			
			
ptree_experiments/settings.py
-------------------------------

- Put the following lines at the top of the file (if they aren't there already)::

	import os
	import os.path

	BASE_DIR = os.path.dirname(os.path.abspath(__file__))

- Change ``DATABASES`` to the following::

	DATABASES = {
		'default': {
			'ENGINE': 'django.db.backends.sqlite3',
			'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
		}
	}

- Change ``TIME_ZONE`` to your time zone (e.g. ``'Europe/Zurich'`` or ``'America/New_York'``).

- In the ``INSTALLED_APPS`` variable, uncomment ``'django.contrib.admin'``.

- After the definition of ``INSTALLED_APPS``, paste the following lines::

    import ptree.settings
    PTREE_EXPERIMENT_APPS = ()
    INSTALLED_APPS = ptree.settings.INSTALLED_APPS + INSTALLED_APPS + PTREE_EXPERIMENT_APPS

ptree_experiments/urls.py
--------------------------

There is a line in ``urls.py`` to enable the admin site URL; uncomment it.

Add the following lines after the definition of ``urlpatterns``::

    import ptree.urls
    urlpatterns += ptree.urls.urlpatterns()