.. _admin:

Experimenter console
********************
You can administer your experiment in your web browser through the experimenter console,
which is accessible at the URL path ``/admin/``.

Here, you can view, create, modify, and delete your objects (experiments, treatments, matches, and players)
through a friendly interface. You can see the results of your experiments as they progress.

The experimenter console contains the links you need to give to your participants.
Go to your app's "Participants" page, and then send each link on that page to a separate participant.
While testing, you should click on these links to see what the experiment looks like.
Note that each link is single use.

Customizing the experimenter console
====================================
You can browse the results of your experiment,
either as it is in progress, or after it is finished.

Usually you will want to see the "Match" or "Participant" tables.

You can customize which fields are displayed by going to ``admin.py`` in your app,
and changing the attributes in ``list_display``, 
which is explained `here <https://docs.djangoproject.com/en/dev/ref/contrib/admin/#django.contrib.admin.ModelAdmin.list_display>`__.

You can also have a column that displays the result of a method on your object,
by specifying the method in ``readonly_fields`` (documented `here <https://docs.djangoproject.com/en/dev/ref/contrib/admin/#django.contrib.admin.ModelAdmin.readonly_fields>`__).
