
from django.db import models


from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType

class AuxiliaryModel(models.Model):
    participant_content_type = models.ForeignKey(ContentType,
                                                 editable=False,
                                                 related_name = '%(app_label)s_%(class)s_participant')
    participant_object_id = models.PositiveIntegerField(editable=False)
    participant = generic.GenericForeignKey('participant_content_type',
                                            'participant_object_id',
                                            )

    match_content_type = models.ForeignKey(ContentType,
                                           editable=False,
                                           related_name = '%(app_label)s_%(class)s_match')
    match_object_id = models.PositiveIntegerField(editable=False)
    match = generic.GenericForeignKey('match_content_type',
                                      'match_object_id',
                                      )

    class Meta:
        abstract = True





