
from django.db import models
import random
import string
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
import itertools

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

def string_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))

def tuple_pairs(items):
    """Django sometimes requires short names and long names for choices in a field.
    When they are the same, you can use this function to avoid duplicating text.
    """

    choices = []
    for item in items:
        choices.append((item, item))
    return tuple(choices)

class RandomCharField(models.CharField):
    """
    We use this for participant code, treatment code, experiment code
    generates gibberish pronounceable words, like 'satonoha' or 'gimoradi'

    # See https://derrickpetzold.com/p/auto-random-character-field-django/
    """

    vowels = list('aeiou')
    consonants = list(set(string.ascii_lowercase) - set(vowels) - set('qxcyw'))

    def find_unique(self, model_instance, value, callback, *args):
        # exclude the current model instance from the queryset used in finding
        # next valid hash
        queryset = model_instance.__class__._default_manager.all()
        if model_instance.pk:
            queryset = queryset.exclude(pk=model_instance.pk)

        # form a kwarg dict used to implement any unique_together constraints
        kwargs = {}
        for params in model_instance._meta.unique_together:
            if self.attname in params:
                for param in params:
                    kwargs[param] = getattr(model_instance, param, None)
        kwargs[self.attname] = value

        while queryset.filter(**kwargs):
            value = callback()
            kwargs[self.attname] = value
        return value

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('blank', True)
        self.length = kwargs.pop('length', 8)
        kwargs['max_length'] = self.length

        super(RandomCharField, self).__init__(*args, **kwargs)

    def generate_chars(self, *args, **kwargs):
        chars = []
        n = self.length
        char_sets = [self.consonants, self.vowels]
        for char_set in itertools.cycle(char_sets):
            n -= 1
            if n < 0:
                break
            chars.append(random.choice(char_set))

        return ''.join(chars)

    def pre_save(self, model_instance, add):
        if not add:
            return getattr(model_instance, self.attname)

        initial = self.generate_chars()
        value = self.find_unique(model_instance, initial, self.generate_chars)
        setattr(model_instance, self.attname, value)
        return value

    def get_internal_type(self):
        return "CharField"

