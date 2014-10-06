from otree.common import money_range
from otree.db import models
import otree.models
import otree.forms

from otree.fields import RandomCharField


class SimpleModel(otree.models.BaseGroup):
    name = models.CharField()


class FormFieldModel(otree.models.BaseGroup):
    null_boolean = models.NullBooleanField()
    big_integer = models.BigIntegerField()
    boolean = models.BooleanField()
    char = models.CharField()
    comma_separated_integer = models.CommaSeparatedIntegerField(max_length=100)
    date = models.DateField()
    date_time = models.DateTimeField()
    alt_date_time = models.DateTimeField(widget=otree.forms.SplitDateTimeWidget)
    decimal = models.DecimalField(max_digits=5, decimal_places=2)
    email = models.EmailField()
    file = models.FileField(upload_to='_tmp/uploads')
    file_path = models.FilePathField()
    float = models.FloatField()
    image = models.ImageField(upload_to='_tmp/uploads')
    ip_address = models.IPAddressField()
    generic_ip_address = models.GenericIPAddressField()
    positive_integer = models.PositiveIntegerField()
    positive_small_integer = models.PositiveSmallIntegerField()
    slug = models.SlugField()
    small_integer = models.SmallIntegerField()
    text = models.TextField()
    alt_text = models.TextField(widget=otree.forms.TextInput)
    time = models.TimeField()
    url = models.URLField()
    many_to_many = models.ManyToManyField('SimpleModel', related_name='+')
    one_to_one = models.OneToOneField('SimpleModel', related_name='+')

    money = models.MoneyField()
    money_choice = models.MoneyField(choices=(
        ('0.01', '0.01'),
        ('1.20', '1.20'),
    ))
    random_char = RandomCharField()

    sent_amount = models.MoneyField(choices=money_range(0, 0.75))
