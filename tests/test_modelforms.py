from django.test import TestCase
import floppyforms
import otree.formfields
from otree.forms_internal import BaseModelForm

from .models import FormFieldModel


class TestModelForm(BaseModelForm):
    class Meta:
        model = FormFieldModel
        exclude = ()


class UseFloppyformWidgetsTests(TestCase):
    def test_overriden_django_fields(self):
        self.assertEqual(TestModelForm.base_fields['char'].__class__, floppyforms.CharField)
        self.assertEqual(TestModelForm.base_fields['null_boolean'].__class__, floppyforms.TypedChoiceField)
        self.assertEqual(TestModelForm.base_fields['big_integer'].__class__, floppyforms.IntegerField)
        self.assertEqual(TestModelForm.base_fields['boolean'].__class__, floppyforms.BooleanField)
        self.assertEqual(TestModelForm.base_fields['char'].__class__, floppyforms.CharField)
        self.assertEqual(TestModelForm.base_fields['comma_separated_integer'].__class__, floppyforms.CharField)
        self.assertEqual(TestModelForm.base_fields['date'].__class__, floppyforms.DateField)
        self.assertEqual(TestModelForm.base_fields['date_time'].__class__, floppyforms.DateTimeField)
        self.assertEqual(TestModelForm.base_fields['decimal'].__class__, floppyforms.DecimalField)
        self.assertEqual(TestModelForm.base_fields['email'].__class__, floppyforms.EmailField)
        self.assertEqual(TestModelForm.base_fields['file'].__class__, floppyforms.FileField)
        self.assertEqual(TestModelForm.base_fields['file_path'].__class__, floppyforms.FilePathField)
        self.assertEqual(TestModelForm.base_fields['float'].__class__, floppyforms.FloatField)
        self.assertEqual(TestModelForm.base_fields['image'].__class__, floppyforms.ImageField)
        self.assertEqual(TestModelForm.base_fields['ip_address'].__class__, floppyforms.IPAddressField)
        self.assertEqual(TestModelForm.base_fields['generic_ip_address'].__class__, floppyforms.GenericIPAddressField)
        self.assertEqual(TestModelForm.base_fields['positive_integer'].__class__, floppyforms.IntegerField)
        self.assertEqual(TestModelForm.base_fields['positive_small_integer'].__class__, floppyforms.IntegerField)
        self.assertEqual(TestModelForm.base_fields['slug'].__class__, floppyforms.SlugField)
        self.assertEqual(TestModelForm.base_fields['small_integer'].__class__, floppyforms.IntegerField)
        self.assertEqual(TestModelForm.base_fields['text'].__class__, floppyforms.CharField)
        self.assertEqual(TestModelForm.base_fields['time'].__class__, floppyforms.TimeField)
        self.assertEqual(TestModelForm.base_fields['url'].__class__, floppyforms.URLField)
        self.assertEqual(TestModelForm.base_fields['many_to_many'].__class__, floppyforms.ModelMultipleChoiceField)
        self.assertEqual(TestModelForm.base_fields['one_to_one'].__class__, floppyforms.ModelChoiceField)

    def test_custom_fields(self):
        self.assertEqual(TestModelForm.base_fields['random_char'].__class__, floppyforms.CharField)
        self.assertEqual(TestModelForm.base_fields['sent_amount'].__class__, floppyforms.TypedChoiceField)

    def test_money_field(self):
        self.assertEqual(TestModelForm.base_fields['money'].__class__, otree.formfields.MoneyField)
        self.assertEqual(TestModelForm.base_fields['money'].widget.__class__, otree.formfields.MoneyInput)
