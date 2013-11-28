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
    first_experiment_content_type = models.ForeignKey(ContentType,
                                                      null=True,
                                                      related_name = '%(app_label)s_%(class)s')
    first_experiment_object_id = models.PositiveIntegerField(null=True)
    first_experiment = generic.GenericForeignKey('first_experiment_content_type',
                                            'first_experiment_object_id',)


    def unicode(self):
        """Define this because Django-Inspect-Model (django-inspect-model.rtfd.org/en/latest/#usage)
        doesn't recognize the __unicode__ method, and Django-data-exports relies on this."""
        if self.name:
            return self.name
        app_labels = []
        experiment = self.first_experiment
        while True:
            app_labels.append(experiment._meta.app_label)
            if experiment.next_experiment:
                experiment = experiment.next_experiment
            else:
                break


        return self.name or str(self.pk)

    def __unicode__(self):
        return unicode(self)

    def add_experiments(self, experiments):
        self.first_experiment = experiments[0]
        for i in range(len(experiments) - 1):
            experiments[i].next_experiment = experiments[i + 1]
            experiments[i + 1].previous_experiment = experiments[i]
            experiments[i].save()
            experiments[i + 1].save()
        self.save()

    class Meta:
        verbose_name_plural = 'sequences of experiments'