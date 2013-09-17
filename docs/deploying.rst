Deploying
*********
Before you launch your app to your audience,
you will need to test it.

The easiest way is to run the website on the personal computer that you are writing the code on.

If you have changed the structure of your models since the last time you deployed, 
you will need to update your database schema with `syncdb <https://docs.djangoproject.com/en/1.5/ref/django-admin/#django-admin-syncdb>`__. Run this::

	python manage.py syncdb --traceback
	
If you need to re-generate your objects (Experiment, Treatments, Players), 
run the command you defined in ref:`management`::
	
	python manage.py [your_app_name]_create_objects --traceback

Finally, you can launch your site on your local machine::

	python manage.py runserver
	
The output of that command should include this::

	Starting development server at http://127.0.0.1:8000/
	
Visit the pTree experimenter console in your browser by appending ``admin`` to the above URL.
You can read more about the experimenter console at ref:`admin`.
	
Deploying on a remote web server
================================

When your app functions properly, you will want to launch it to your audience 
by deploying it from your personal computer to a web server,
so that users can access it from a URL.

pTree can run with any operating system, database engine, or web server supported by Django.

The easiest option I have found is `Heroku <https://www.heroku.com/>`,
a website hosting service that greatly simplifies the amount of configuration and maintenance you need to do.
Once you have created a free account, 
you can follow the instructions `here <https://devcenter.heroku.com/articles/getting-started-with-django>`__.

You can create multiple `environments <https://devcenter.heroku.com/articles/multiple-environments>`__. 
For example, if your users access the experiment at mysite.com,
you can have a separate site called development.mysite.com
where you can test the site before launching.
