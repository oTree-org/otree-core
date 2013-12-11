from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from django.conf import settings
from django.utils.importlib import import_module
from django.contrib.contenttypes.management import update_all_contenttypes
from data_exports.models import Format, Export, Column
import data_exports.models
from django.contrib.contenttypes.models import ContentType
from django.template.defaultfilters import slugify

from django.contrib.auth import models as auth_models
from django.contrib.auth.management import create_superuser
from django.db.models import signals
import ptree.common
import ptree.settings
import ptree.models
from django.contrib import admin
from django.contrib.contenttypes.management import update_all_contenttypes
from ptree.sequence_of_experiments.models import StubModel

def create_default_superuser(app, created_models, verbosity, **kwargs):
    """
    Creates our default superuser.
    """
    username = settings.ADMIN_USERNAME
    password = settings.ADMIN_PASSWORD
    email = getattr(settings, 'ADMIN_EMAIL', '')
    try:
        auth_models.User.objects.get(username=username)
    except auth_models.User.DoesNotExist:
        s = '\n'.join(['Creating default superuser.',
             'Username: {}'.format(username),
             'Email: {}'.format(email)])
        assert auth_models.User.objects.create_superuser(username, email, password)
    else:
        print 'Default superuser already exists.'

if getattr(settings, 'CREATE_DEFAULT_SUPERUSER', False):
    # From http://stackoverflow.com/questions/1466827/:
    # Prevent interactive question about wanting a superuser created.
    # (This code has to go in this otherwise empty "models" module
    # so that it gets processed by the "syncdb" command during
    # database creation.)
    signals.post_syncdb.disconnect(
        create_superuser,
        sender=auth_models,
        dispatch_uid='django.contrib.auth.management.create_superuser'
    )

    # Trigger default superuser creation.
    signals.post_syncdb.connect(
        create_default_superuser,
        sender=auth_models,
        dispatch_uid='common.models.create_testuser'
    )

def create_html_export_format(sender, **kwargs):
    name = 'HTML'
    try:
        Format.objects.get(name = name)
    except Format.DoesNotExist:
        html_format = Format(name=name,
                            file_ext="html",
                            mime="text/html",
                            template="data_exports/ptree.html")
        html_format.save()


def create_csv_export_format(sender, **kwargs):
    name = 'CSV'
    try:
        Format.objects.get(name = name)
    except Format.DoesNotExist:
        csv_format = Format(name=name,
                            file_ext="csv",
                            mime="text/csv",
                            template="data_exports/ptree.csv")
        csv_format.save()

def create_export(content_type, export_name, fields, format_name="CSV"):

    model_name = '{}: {} ({})'.format(content_type.app_label,
                                      export_name,
                                      format_name)
    # delete if it already exists
    Export.objects.filter(name = model_name).delete()

    csv_format = Format.objects.get(name=format_name)
    export = Export(name = model_name,
                    slug = slugify(model_name),
                    model = content_type,
                    export_format = csv_format)
    export.save()

    for i, field in enumerate(fields):
        column = Column(export = export,
                        column = field,
                        label = field,
                        order = i)
        column.save()

def create_export_for_participants(app_label, Participant):
    participant_content_type = ContentType.objects.get(app_label=app_label, model='participant')
    list_display = ptree.common.get_participant_list_display(Participant,
                                                      ptree.common.get_participant_readonly_fields([]))
    create_export(participant_content_type,
                       'participants',
                       list_display)

def create_export_for_matches(app_label, Match):
    match_content_type = ContentType.objects.get(app_label=app_label, model='match')
    list_display = ptree.common.get_match_list_display(Match,
                                                      ptree.common.get_match_readonly_fields([]))
    create_export(match_content_type,
                       'matches',
                       list_display)

def create_export_for_treatments(app_label, Treatment):
    treatment_content_type = ContentType.objects.get(app_label=app_label, model='treatment')
    list_display = ptree.common.get_treatment_list_display(Treatment,
                                                      ptree.common.get_treatment_readonly_fields([]))
    create_export(treatment_content_type,
                       'treatments',
                       list_display)

def create_export_for_experiments(app_label, Experiment):
    experiment_content_type = ContentType.objects.get(app_label=app_label, model='experiment')
    list_display = ptree.common.get_experiment_list_display(Experiment,
                                                      ptree.common.get_experiment_readonly_fields([]))
    create_export(experiment_content_type,
                       'experiments',
                       list_display)

def create_all_data_exports(sender, **kwargs):
    # only do it for 1 sender, so that these lines don't get repeated for every app
    if sender.__name__ == 'django.contrib.auth.models':
        update_all_contenttypes()
        create_html_export_format(sender)
        create_csv_export_format(sender)
        for app_label in settings.INSTALLED_PTREE_APPS:
            print 'Creating data exports for {}'.format(app_label)
            models_module = import_module('{}.models'.format(app_label))
            # this assumes they all exist, which is a core part of pTree design
            create_export_for_matches(app_label, models_module.Match)
            create_export_for_participants(app_label, models_module.Participant)
            create_export_for_treatments(app_label, models_module.Treatment)
            create_export_for_experiments(app_label, models_module.Experiment)
    StubModel().save()

signals.post_syncdb.connect(create_all_data_exports)

# create a single instance so it can be used for empty ModelForms.



