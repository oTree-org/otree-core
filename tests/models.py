from decimal import Decimal
from otree.common import currency_range
from otree.db import models
import otree.models
import otree.forms


class SimpleModel(otree.models.BaseGroup):
    name = models.CharField()

    def name_choices(self):
        return [(self.name, self.name.upper())]


class BoundFieldModel(otree.models.BaseGroup):
    upper_bound = 9999

    big_integer = models.BigIntegerField(null=True, blank=True)
    currency = models.CurrencyField(null=True, blank=True)
    decimal = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    integer = models.IntegerField(null=True, blank=True)
    integer_no_bounds = models.IntegerField(null=True, blank=True)
    positive_integer = models.PositiveIntegerField(null=True, blank=True)
    small_integer = models.SmallIntegerField(null=True, blank=True)
    small_positive_integer = models.SmallIntegerField(null=True, blank=True)

    def currency_bounds(self):
        return [0, 0.5]

    def decimal_bounds(self):
        return [0.111, Decimal('1') / Decimal('3')]

    def big_integer_bounds(self):
        return [0, 10**10]

    def integer_bounds(self):
        return [-5, self.upper_bound]

    def positive_integer_bounds(self):
        return [0, 10]

    def small_integer_bounds(self):
        return [-1, 1]

    def small_positive_integer_bounds(self):
        return [0, 1]


class FormFieldModel(otree.models.BaseGroup):
    null_boolean = models.NullBooleanField()
    big_integer = models.BigIntegerField()
    boolean = models.BooleanField(default=False)
    char = models.CharField()
    comma_separated_integer = models.CommaSeparatedIntegerField(max_length=100)
    date = models.DateField()
    date_time = models.DateTimeField()
    alt_date_time = models.DateTimeField(
        widget=otree.forms.SplitDateTimeWidget
    )
    decimal = models.DecimalField(max_digits=5, decimal_places=2)
    email = models.EmailField()
    file = models.FileField(upload_to='_tmp/uploads')
    file_path = models.FilePathField()
    float = models.FloatField()
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

    currency = models.CurrencyField()
    currency_choice = models.CurrencyField(choices=(
        ('0.01', '0.01'),
        ('1.20', '1.20'),
    ))
    random_char = models.RandomCharField()

    sent_amount = models.CurrencyField(choices=currency_range(0, 0.75, 0.05))
