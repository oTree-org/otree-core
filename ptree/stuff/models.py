from django.db import models
import ptree.models.common
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType

class StubModel(models.Model):
    """To be used as the model for an empty form, so that form_class can be omitted."""
    stub_field = models.BooleanField(default=True)

class SequenceOfExperiments(models.Model):
    name = models.CharField(max_length = 300, null = True, blank = True)
    code = ptree.models.common.RandomCharField()
    first_experiment_content_type = models.ForeignKey(ContentType, null=True)
    first_experiment_object_id = models.PositiveIntegerField(null=True)
    first_experiment = generic.GenericForeignKey('first_experiment_content_type',
                                            'first_experiment_object_id',)


    def add_experiments(self, experiments):
        self.first_experiment = experiments[0]
        for i in range(len(experiments) - 1):
            experiments[i].next_experiment = experiments[i + 1]
            experiments[i].save()
        self.save()