from django.test import TestCase
from django.template import Template

from otree.checks.templates import get_unreachable_content


class TemplateCheckTest(TestCase):
    def test_non_extending_template(self):
        template = Template('''Stuff in here.''')
        content = get_unreachable_content(template)
        self.assertFalse(content)

        template = Template('''{% block head %}Stuff in here.{% endblock %}''')
        content = get_unreachable_content(template)
        self.assertFalse(content)

        template = Template(
            '''
            Free i am.
            {% block head %}I'm not :({% endblock %}
            ''')
        content = get_unreachable_content(template)
        self.assertEqual(content, [])

    def test_ok_extending_template(self):
        template = Template(
            '''
            {% extends "base.html" %}

            {% block content %}
            Stuff in here.
            {% if 1 %}Un-Conditional{% endif %}
            {% endblock %}
            ''')

        content = get_unreachable_content(template)
        self.assertEqual(content, [])

    def test_extending_template_with_non_wrapped_code(self):
        template = Template(
            '''
            {% extends "base.html" %}

            Free i am.

            {% block content %}Stuff in here.{% endblock %}
            ''')

        content = get_unreachable_content(template)
        self.assertEqual(len(content), 1)
        self.assertTrue('Free i am.' in content[0])
        self.assertTrue('Stuff in here.' not in content[0])

    def test_text_after_block(self):
        template = Template(
            '''
            {% extends "base.html" %}
            {% block content %}Stuff in here.{% endblock %}
            After the block.
            ''')

        content = get_unreachable_content(template)
        self.assertEqual(len(content), 1)
        self.assertTrue('After the block.' in content[0])
        self.assertTrue('Stuff in here.' not in content[0])

    def test_multiple_text_nodes(self):
        template = Template(
            '''
            {% extends "base.html" %}
            First.
            {% block content %}Stuff in here.{% endblock %}
            Second.
            {% load i18n %}
            Third.
            ''')

        content = get_unreachable_content(template)
        self.assertEqual(len(content), 3)
        self.assertTrue('First.' in content[0])
        self.assertTrue('Second.' in content[1])
        self.assertTrue('Third.' in content[2])

    def test_non_block_statements(self):
        # We do not dive into other statements.
        template = Template(
            '''
            {% extends "base.html" %}

            {% if 1 %}
            Free i am.
            {% endif %}
            ''')

        content = get_unreachable_content(template)
        self.assertEqual(len(content), 0)
