The ``templates/`` directory
============================

Your ``templates/`` directory will contain the templates for the HTML
that gets displayed to the participant.

ptree uses `Django's template system <https://docs.djangoproject.com/en/dev/topics/templates/>`_.

Template configuration
~~~~~~~~~~~~~~~~~~~~~~

Each template needs a few lines of code at the top.

Base template
-------------

Put this line at the top of your file::

    {% extends "ptree/Base.html" %}

Now, instead of having to write all your HTML from scratch, for example::

    <!DOCTYPE html>
    <html lang="en">
        <head>
        <!-- and so on... -->
    
You just have to define 2 blocks::

    {% block title %}
        Title goes here
    {% endblock %}
    
    {% block content %}
        Body HTML goes here.
    {% endblock %}

You may want to define your own base template rather than using ptree's built-in base template.
This is useful when you want to customize the appearance or functionality (e.g. by adding custom CSS or JavaScript),
or customize the structure of HTML headings. This is easily done.
Just follow the instructions `here <https://docs.djangoproject.com/en/dev/topics/templates/#template-inheritance>`__.

Custom filters
--------------

The following line will load ptree's filter module::
    
    {% load ptreefilters %}
    
Currently, the main filter in this module is the ``currency`` filter,
which formats integers as currency amounts.

For example, if you pass to your template a variable called ``some_number`` that is equal to ``142``,
``{{ some_number|currency }}`` would display it to the participant as "$1.42".

You can customize this behavior or even create your own tags and filters,
by following the documentation `here <https://docs.djangoproject.com/en/dev/howto/custom-template-tags/>`__.

Static files
------------

You will likely want to include images, CSS, or JavaScript in your pages.

To do that, put the following line in your template::

    {% load staticfiles %}

And follow the instructions `here <https://docs.djangoproject.com/en/dev/howto/static-files/>`__.

Forms
~~~~~

Each page should include a form.
Even if the page is empty, it should contain an empty form with a submit button
(which will say "Next") so that the participant can go to the next page.

Just paste this in the location where your form should be,
and ptree will make sure the form gets displayed and formatted properly::

    {% include "ptree/Form.html" %}
    
Making your page look great
~~~~~~~~~~~~~~~~~~~~~~~~~~~

ptree comes with `Bootstrap <http://getbootstrap.com/>`__, a very popular library for customizing a website's participant interface.

You can use it if you want a custom `style <http://getbootstrap.com/css/>`__,
or a specific `component <http://getbootstrap.com/components/>`__    
like a table, alert, progress bar, label, etc.
You can even make your page dynamic with elements like `popovers <http://getbootstrap.com/javascript/#popovers>`__, 
`modals <http://getbootstrap.com/javascript/#modals>`__, 
and `collapsible text <http://getbootstrap.com/javascript/#collapse>`__.

Bootstrap is very easy to use and well documented.
Usually you just need to add a ``class=`` attribute to your HTML element,
and Bootstrap will take care of the rest.

For example, the following HTML will create a "Success" alert::

    <div class="alert alert-success">Great job!</div>
    
Smartphones and tablets    
~~~~~~~~~~~~~~~~~~~~~~~

Since ptree uses Bootstrap for its participant interface, 
your ptree app should work on all major browsers (Chrome/Internet Explorer/Firefox/Safari).
When participants visit on a smartphone or tablet (e.g. iPhone/Android/etc.),
they should see an appropriately scaled down "mobile friendly" version of the site.
This will generally not require any effort on your part since Bootstrap does it automatically,
but if you plan to deploy your app to participants on mobile devices,
you should test it out on a mobile device during development,
since some HTML code doesn't look good on mobile devices.

