from otree.db import models
import otree.models


class SimpleModel(otree.models.BaseMatch):
    name = models.CharField()


class FormFieldModel(otree.models.BaseMatch):
    money = models.MoneyField()
    null_boolean = models.NullBooleanField()
    big_integer = models.BigIntegerField()
    boolean = models.BooleanField()
    char = models.CharField()
    comma_separated_integer = models.CommaSeparatedIntegerField()
    date = models.DateField()
    date_time = models.DateTimeField()
    decimal = models.DecimalField()
    email = models.EmailField()
    file = models.FileField()
    file_path = models.FilePathField()
    float = models.FloatField()
    image = models.ImageField()
    ip_address = models.IPAddressField()
    generic_ip_address = models.GenericIPAddressField()
    positive_integer = models.PositiveIntegerField()
    positive_small_integer = models.PositiveSmallIntegerField()
    slug = models.SlugField()
    small_integer = models.SmallIntegerField()
    text = models.TextField()
    time = models.TimeField()
    url = models.URLField()
    many_to_many = models.ManyToManyField('SimpleModel')
    one_to_one = models.OneToOneField('SimpleModel')
