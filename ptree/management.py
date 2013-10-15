from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from data_exports.models import Format, Export, Column
from django.contrib.contenttypes.models import ContentType
from django.template.defaultfilters import slugify


class CreateObjectsCommand(BaseCommand):
    help = "pTree: Populate the database before launching, with Experiment, Treatments, and Participant objects."
    self.app_label = None # child classes need to fill this in.

    option_list = BaseCommand.option_list + (
        make_option('--participants',
            type='int',
            dest='num_participants',
            help='Number of participants to pre-generate'),
    )

    def create_objects(self, num_participants):
        raise NotImplementedError()

    def create_csv_export_for_start_urls(app_label):
        # add this export format to the given models.
        model_name = '{}: start URLs'.format(app_label)
        csv_format = Format.objects.get(name="CSV")
        export = Export(name = model_name,
                        slug = slugify(model_name),
                        model = ContentType.objects.get(app_label=app_label, model='participant'),
                        export_format = csv_format)
        export.save()

        column = Column(export = export,
                        column = 'start_url',
                        label = 'start_url',
                        order = 0)
        column.save()


    def handle(self, *args, **options):
        num_participants = options['num_participants']
        self.create_objects(num_participants)
        self.create_csv_export_for_start_urls()
        print 'Created objects for {}'.format(self.app_label)