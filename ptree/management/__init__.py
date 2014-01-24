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
from ptree.session.models import StubModel
import ptree.adminlib
from django.db import models
from data_exports.compat import python_2_unicode_compatible

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




def create_export(app_label):
    participant_content_type = ContentType.objects.get(app_label=app_label, model='participant')

    model_names_as_attributes = {
        "Participant": None,
        'Match': 'match',
        'Treatment': 'treatment',
        'Experiment': 'experiment',
        'SessionParticipant': 'session_participant',
        'Session': 'session',
    }


    format_name = "CSV"
    export_name = '{} participants'.format(participant_content_type.app_label)

    # delete if it already exists
    Export.objects.filter(name = export_name).delete()

    csv_format = Format.objects.get(name=format_name)
    export = Export(name = export_name,
                    slug = slugify(export_name),
                    model = participant_content_type,
                    export_format = csv_format)
    export.save()

    export_fields = ptree.adminlib.get_data_export_fields(app_label)
    export_field_tuples = []
    for model_name in ptree.adminlib.MODEL_NAMES:
        if model_name == "Participant":
            export_field_tuples.extend((field, field) for field in export_fields[model_name])
        else:
            for field in export_fields[model_name]:
                dot_path = '{}.{}'.format(model_names_as_attributes[model_name], field)
                export_field_tuples.append((dot_path, dot_path))
    for i, tup in enumerate(export_field_tuples):
        path, path = tup
        column = Column(export = export,
                        column = path,
                        label = path,
                        order = i)
        column.save()

def create_all_data_exports(sender, **kwargs):
    StubModel().save()
    # only do it for 1 sender, so that these lines don't get repeated for every app
    if sender.__name__ == 'django.contrib.auth.models':
        update_all_contenttypes()
        create_csv_export_format(sender)
        for app_label in settings.INSTALLED_PTREE_APPS:
            if ptree.common.is_experiment_app(app_label):
                print 'Creating data exports for {}'.format(app_label)
                create_export(app_label)


signals.post_syncdb.connect(create_all_data_exports)

# create a single instance so it can be used for empty ModelForms.



