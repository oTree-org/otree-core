Setup
~~~~~

Install
===================

On your command line, type ``pip install django-ptree``.

pTree is built on top of Django, 
which is the most popular web development framework for Python.
When you install pTree, Django will get installed automatically.

Create your project
===================

Each pTree experiment type is implemented as a Django app.
For example, if you want to create the prisoner's dilemma, trust game, and public goods game,
those would be 3 separate apps. 

Before you create your apps, you need to create a Django project that will contain them.

From the command line, ``cd`` into a directory where you'd like to store your
code (can be anywhere, like a folder in "My Documents" or "Documents"), 
then run the following command::

   django-admin.py startproject --template=http://is.gd/ptree_project ptree_experiments

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

Open your project for editing
=============================

Launch PyCharm, and select "Open Directory".
Navigate to the outer ``ptree_experiments`` directory (not the subfolder that has the same name) and click OK.
When the project opens, on the left-hand site you should see a directory tree that expands to the following::

    ptree_experiments/
        manage.py
        ptree_experiments/
            __init__.py
            settings.py
            urls.py
            wsgi.py