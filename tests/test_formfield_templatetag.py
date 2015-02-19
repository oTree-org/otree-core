from django.core.management import call_command
from django.template import Context
from django.template import Template
from django.template import TemplateSyntaxError
from django.template import VariableDoesNotExist
from django.test import TestCase

import otree.db.models
import otree.forms

from tests.simple_game.models import Player
from tests.utils import capture_stdout


class SimplePlayer(otree.db.models.Model):
    name = otree.db.models.CharField(max_length=50, blank=True)
    age = otree.db.models.IntegerField(default=30, null=True, blank=True)


class PlayerForm(otree.forms.ModelForm):
    class Meta:
        model = Player
        fields = ('my_field',)


class SimplePlayerForm(otree.forms.ModelForm):
    class Meta:
        model = SimplePlayer
        fields = ('name', 'age',)


class FormFieldTestMixin(TestCase):
    def setUp(self):
        with capture_stdout():
            call_command('create_session', 'simple_game', 1)
        self.player = Player.objects.first()
        self.simple_player = SimplePlayer.objects.create()

    def parse(self, fragment):
        return Template('{% load otree_tags %}' + fragment)

    def render(self, fragment, context=None):
        if context is None:
            context = Context()
        if not isinstance(context, Context):
            context = Context(context)
        return self.parse(fragment).render(context)


class FormFieldSyntaxTests(FormFieldTestMixin, TestCase):
    def test_fail_for_no_arguments(self):
        with self.assertRaises(TemplateSyntaxError):
            self.parse('{% formfield %}')

    def test_fail_when_multiple_fields_are_given(self):
        with self.assertRaises(TemplateSyntaxError):
            self.parse('{% formfield field field2 %}')

    def test_fail_with_no_arguments_after_with(self):
        with self.assertRaises(TemplateSyntaxError):
            self.parse('{% formfield field with %}')

    def test_fail_with_bad_arguments_after_with(self):
        with self.assertRaises(TemplateSyntaxError):
            self.parse('{% formfield field with label %}')
        with self.assertRaises(TemplateSyntaxError):
            self.parse('{% formfield field with -=- %}')
        with self.assertRaises(TemplateSyntaxError):
            self.parse('{% formfield field with label="Right" wrong %}')

    def test_one_field_is_given(self):
        self.parse('{% formfield field %}')
        self.parse('{% formfield player.field %}')
        self.parse('{% formfield player.soso.deeply.nested.field %}')

    def test_with_syntax(self):
        self.parse('{% formfield field with label="Hello" %}')
        self.parse('{% formfield field with help_text=variable %}')
        self.parse('''
            {% formfield field with label=label_value help_text="Constant" %}
        ''')


class FormFieldTests(FormFieldTestMixin, TestCase):
    def test_bound_field_displayed(self):
        form = SimplePlayerForm(instance=self.simple_player)
        rendered = self.render('{% formfield form.name %}', {
            'form': form
        })
        self.assertInHTML(
            '''
            <input type="text" id="id_name" name="name" class="form-control"
                maxlength="50">
            ''', rendered)
        # Label is there.
        self.assertInHTML(
            '''
            <label for="id_name">Name:</label>
            ''', rendered)

    def test_model_field_displayed(self):
        form = SimplePlayerForm(instance=self.simple_player)
        rendered = self.render('{% formfield player.name %}', {
            'form': form,
            'player': self.simple_player,
        })
        self.assertInHTML(
            '''
            <input type="text" id="id_name" name="name" class="form-control"
                maxlength="50">
            ''', rendered)
        # Label is there.
        self.assertInHTML(
            '''
            <label for="id_name">Name:</label>
            ''', rendered)

    def test_prefilled_model_field_displayed(self):
        player = SimplePlayer(name='Jack')
        form = SimplePlayerForm(instance=player)
        rendered = self.render('{% formfield player.name %}', {
            'form': form,
            'player': player,
        })
        self.assertInHTML(
            '''
            <input type="text" id="id_name" name="name" class="form-control"
                maxlength="50" value="Jack">
            ''', rendered)

    def test_variable_is_none(self):
        form = SimplePlayerForm(instance=self.simple_player)
        with self.assertRaises(VariableDoesNotExist):
            self.render('{% formfield player.name %}', {
                'form': form,
                'player': None,
            })
        # Not set at all.
        with self.assertRaises(VariableDoesNotExist):
            self.render('{% formfield player.name %}', {
                'form': form,
            })

    def test_variable_is_no_model_instance(self):
        form = SimplePlayerForm(instance=self.simple_player)

        with self.assertRaises(ValueError) as cm:
            self.render('{% formfield player.name %}', {
                'form': form,
                'player': {
                    'name': 'Jack',
                }
            })

        self.assertTrue("'player.name'" in str(cm.exception))
        # The representation of the variable is also included.
        self.assertTrue("Jack" in str(cm.exception))

    def test_variable_different_to_form_instance(self):
        player1 = SimplePlayer.objects.create()
        player2 = SimplePlayer.objects.create()
        form = SimplePlayerForm(instance=player1)

        # Different model instance of the same type.
        with self.assertRaises(ValueError) as cm:
            self.render('{% formfield player.name %}', {
                'form': form,
                'player': player2,
            })
        self.assertTrue("'player'" in str(cm.exception))

    def test_model_field_not_part_of_form(self):
        form = SimplePlayerForm(instance=self.simple_player)

        # Different model instance of the same type.
        with self.assertRaises(ValueError) as cm:
            self.render('{% formfield player.unkown_field %}', {
                'form': form,
                'player': self.simple_player,
            })
        self.assertTrue("'unkown_field'" in str(cm.exception))

    def test_no_form_in_context(self):
        form = SimplePlayerForm(instance=self.simple_player)

        # Different model instance of the same type.
        with self.assertRaises(VariableDoesNotExist) as cm:
            self.render('{% formfield player.unkown_field %}', {
                'form_alternative': form,
                'player': self.simple_player,
            })

        # The exception should talk about the formfield tag and the form
        # variable.
        self.assertTrue("'formfield'" in str(cm.exception))
        self.assertTrue("'form'" in str(cm.exception))

    def test_override_label(self):
        form = SimplePlayerForm(instance=self.simple_player)
        rendered = self.render(
            '{% formfield player.name with label="A fancy label" %}',
            {
                'form': form,
                'player': self.simple_player,
            })
        # Label is there.
        self.assertInHTML(
            '''
            <label for="id_name">A fancy label:</label>
            ''', rendered)
