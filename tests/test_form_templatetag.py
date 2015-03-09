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


class SimplePlayerForm(otree.forms.ModelForm):
    class Meta:
        model = SimplePlayer
        fields = ('name', 'age',)


class FormFieldTestMixin(TestCase):
    def setUp(self):
        self.simple_player = SimplePlayer.objects.create()

    def parse(self, fragment):
        return Template('{% load otree_tags %}' + fragment)

    def render(self, fragment, context=None):
        if context is None:
            context = Context()
        if not isinstance(context, Context):
            context = Context(context)
        return self.parse(fragment).render(context)


class CheckAllFieldsAreRenderedTests(FormFieldTestMixin, TestCase):
    def test_rendering_works(self):
        class OnlyNameForm(otree.forms.ModelForm):
            class Meta:
                model = SimplePlayer
                fields = ('name',)

        form = OnlyNameForm(instance=self.simple_player)
        with self.assertTemplateNotUsed(
                template_name='otree/forms/_formfield_is_missing_error.html'):
            result = self.render(
                '''
                {% pageform form using %}
                    {% formfield player.name %}
                {% endpageform %}
                ''',
                context={'form': form, 'player': self.simple_player})

        self.assertTrue('<input' in result)
        self.assertTrue('name="name"' in result)

        form = SimplePlayerForm(instance=self.simple_player)
        with self.assertTemplateNotUsed('otree/forms/_formfield_is_missing_error.html'):
            result = self.render(
                '''
                {% pageform form using %}
                    {% formfield player.name %}
                    {% formfield player.age %}
                {% endpageform %}
                ''',
                context={'form': form, 'player': self.simple_player})

    def test_rendering_complains_when_not_all_fields_are_rendered(self):
        form = SimplePlayerForm(instance=self.simple_player)
        with self.assertTemplateUsed('otree/forms/_formfield_is_missing_error.html'):
            self.render(
                '{% pageform form using %}{% formfield player.name %}{% endpageform %}',
                context={'form': form, 'player': self.simple_player})
