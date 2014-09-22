from django.test import TestCase
import floppyforms.widgets

import otree.widgets


class BasicWidgetTests(TestCase):
    def test_all_widgets_are_available(self):
        for widget_name in floppyforms.widgets.__all__:
            self.assertTrue(hasattr(otree.widgets, widget_name),
                            'otree.widgets is missing the widget {0}'.format(
                                widget_name))
