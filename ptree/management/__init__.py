from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from data_exports.models import Format, Export, Column
import data_exports.models
from django.contrib.contenttypes.models import ContentType
from django.template.defaultfilters import slugify

from django.conf import settings
from django.contrib.auth import models as auth_models
from django.contrib.auth.management import create_superuser
from django.db.models import signals


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
    try:
        Format.objects.get(name = 'CSV')
    except Format.DoesNotExist:
        csv_format = Format(name="CSV",
                            file_ext="csv",
                            mime="text/csv",
                            template="data_exports/ptree_csv.html")
        csv_format.save()

signals.post_syncdb.connect(
    create_csv_export_format,
    sender=data_exports.models,
)

class CreateObjectsCommand(BaseCommand):
    help = "pTree: Populate the database before launching, with Experiment, Treatments, and Participant objects."
    app_label = None # child classes need to fill this in.

    option_list = BaseCommand.option_list + (
        make_option('--participants',
            type='int',
            dest='num_participants',
            help='Number of participants to pre-generate'),
    )

    def create_objects(self, num_participants):
        raise NotImplementedError()

    def create_export_for_start_urls(self):
        # add this export format to the given models.
        model_name = '{}: start URLs (CSV)'.format(self.app_label)
        csv_format = Format.objects.get(name="CSV")
        export = Export(name = model_name,
                        slug = slugify(model_name),
                        model = ContentType.objects.get(app_label=self.app_label, model='participant'),
                        export_format = csv_format)
        export.save()

        column = Column(export = export,
                        column = 'start_url',
                        label = 'start_url',
                        order = 0)
        column.save()

    def create_export_for_payments(self):
        # add this export format to the given models.
        model_name = '{}: payments (CSV)'.format(self.app_label)
        csv_format = Format.objects.get(name="CSV")
        export = Export(name = model_name,
                        slug = slugify(model_name),
                        model = ContentType.objects.get(app_label=self.app_label, model='participant'),
                        export_format = csv_format)
        export.save()

        column = Column(export = export,
                        column = 'code',
                        label = 'code',
                        order = 0)
        column.save()

        column = Column(export = export,
                        column = 'total_pay',
                        label = 'total_pay',
                        order = 1)
        column.save()


    def handle(self, *args, **options):
        num_participants = options['num_participants']
        self.create_objects(num_participants)
        self.create_export_for_start_urls()
        self.create_export_for_payments()
        print 'Created objects for {}'.format(self.app_label)


