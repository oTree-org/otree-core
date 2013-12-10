from django.db import models
from ptree.fields import RandomCharField
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType



class StubModel(models.Model):
    """To be used as the model for an empty form, so that form_class can be omitted."""

class SequenceOfExperiments(models.Model):
    name = models.CharField(max_length = 300, null = True, blank = True)
    code = RandomCharField(length=8)
    first_experiment_content_type = models.ForeignKey(ContentType,
                                                      null=True,
                                                      related_name = '%(app_label)s_%(class)s')
    first_experiment_object_id = models.PositiveIntegerField(null=True)
    first_experiment = generic.GenericForeignKey('first_experiment_content_type',
                                            'first_experiment_object_id',)

    is_for_mturk = models.BooleanField(verbose_name='Is for MTurk', default=True)
    payment_was_sent = models.BooleanField(default=False)
    pregenerate_matches = models.BooleanField(default=False)


    def unicode(self):
        """Define this because Django-Inspect-Model (django-inspect-model.rtfd.org/en/latest/#usage)
        doesn't recognize the __unicode__ method, and Django-data-exports relies on this."""
        if self.name:
            return self.name
        experiment_names = []

        for experiment in self.experiments():
            experiment_names.append('{} {}'.format(experiment._meta.app_label, experiment))
        return ', '.join(experiment_names)

    unicode.short_description = 'Name'

    def experiments(self):
        lst = []
        experiment = self.first_experiment
        while True:
            lst.append(experiment)
            experiment = experiment.next_experiment
            if not experiment:
                break
        return lst


    def __unicode__(self):
        return self.unicode()

    def add_experiments(self, experiments):
        self.first_experiment = experiments[0]
        for i in range(len(experiments) - 1):
            experiments[i].next_experiment = experiments[i + 1]
            experiments[i + 1].previous_experiment = experiments[i]
        for experiment in experiments:
            experiment.sequence_of_experiments = self
            experiment.save()
        self.save()

    def participants(self):
        return self.participant_set.all()

    class Meta:
        verbose_name_plural = 'sequences of experiments'

class Participant(models.Model):

    sequence_of_experiments = models.ForeignKey(SequenceOfExperiments)

    was_terminated = models.BooleanField(default=False)
    mturk_assignment_id = models.CharField(max_length = 50, null = True)
    mturk_worker_id = models.CharField(max_length = 50, null = True)
    ip_address = models.IPAddressField(null = True)

    # unique=True can't be set, because the same external ID could be reused in multiple sequences.
    # however, it should be unique within the sequence.
    external_id = models.CharField(max_length = 50,
                               null = True,
                               )

    def unicode(self):
        return self.external_id or str(self.pk)

    def __unicode__(self):
        return self.unicode()

    class Meta:
        ordering = ['pk']

