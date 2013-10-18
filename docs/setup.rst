Setup
~~~~~

Choose a location for your ptree work
======================================

Choose where on your computer you want to store your ptree work.
It can be anywhere, like a folder in "My Documents" or "Documents".

Create a directory called 'ptree'.

Create a virtualenv
====================

Open the 'ptree' directory in your command line,
and type the following command::

    virtualenv venv

This will create an isolated Python environment.
This means you won't need administrator permissions to install libraries.
It also means that your your ptree programs will not break when a system-wide Python library is updated,
so your ptree experiment will still run the same way a year from now.

You can read more about virtualenv `here <https://pypi.python.org/pypi/virtualenv>`__.

Mac
---

Go to your home directory (which appears in the sidebar of Finder windows),
and create a new file in TextEdit called '.bash_profile' (or open it if it already exists).
Add the following line::

    source /home/[path to your ptree directory]/venv/bin/activate

Then save and close the file. Open a new Terminal window.
You should see ``(venv)`` at the beginning of your prompt.

Windows
--------

In PowerShell, type::

    notepad $profile

(You may be prompted to create a new file, which you should do.)
Add the following line (including the dot at the beginning)::

    . "C:\[path to your virtual environment]\venv\Scripts\activate.ps1"
    
Then save and close the file. Open a new PowerShell window.
You should see ``(venv)`` at the beginning of your prompt.

Install ptree
===================

On your command line, type ``pip install django-ptree``.

ptree is built on top of Django, 
which is the most popular web development framework for Python.
When you install ptree, Django will get installed automatically.

Create your project
===================

Each ptree experiment type is implemented as a Django app.
For example, if you want to create the prisoner's dilemma, trust game, and public goods game,
those would be 3 separate apps. 

Before you create your apps, you need to create a Django project that will contain them.

then run the following command::

   ptree startproject ptree_experiments

.. note::

    On Windows, you may have to do ``python venv\Scripts\ptree startproject ptree_experiments``
    
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

