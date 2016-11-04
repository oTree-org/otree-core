# mocking the public API for PyCharm autocomplete.
# one downside is that PyCharm doesn't seem to fully autocomplete arguments
# in the .pyi. It gives the yellow pop-up, but doesn't complete what you
# are typing.

def Submission(PageClass, post_data: dict={}, check_html=True): pass
def SubmissionMustFail(PageClass, post_data: dict={}, check_html=True): pass

class models:

    def __getattr__(self, item):
        pass

    class BooleanField(object):
        def __init__(
                self,
                *,
                choices=None,
                widget=None,
                initial=None,
                verbose_name=None,
                doc='',
                null=True,
                help_text='',
                **kwargs):
            pass

    class CharField(object):
        def __init__(
                self,
                *,
                choices=None,
                widget=None,
                initial=None,
                verbose_name=None,
                doc='',
                max_length=500,
                blank=False,
                null=True,
                help_text='',
                **kwargs):
            pass

    # need to copy-paste the __init__ between
    # PositiveInteger, Integer, Float, and Currency
    # because if I use inheritance, PyCharm doesn't auto-complete
    # while typing args

    class PositiveIntegerField:
        def __init__(
            self,
            *,
            choices=None,
            widget=None,
            initial=None,
            verbose_name=None,
            doc='',
            min=None,
            max=None,
            blank=False,
            null=True,
            help_text='',
            **kwargs):
                pass

    class IntegerField:
        def __init__(
            self,
            *,
            choices=None,
            widget=None,
            initial=None,
            verbose_name=None,
            doc='',
            min=None,
            max=None,
            blank=False,
            null=True,
            help_text='',
            **kwargs):
                pass

    class FloatField:
        def __init__(
            self,
            *,
            choices=None,
            widget=None,
            initial=None,
            verbose_name=None,
            doc='',
            min=None,
            max=None,
            blank=False,
            null=True,
            help_text='',
            **kwargs):
                pass

    class CurrencyField:
        def __init__(
            self,
            *,
            choices=None,
            widget=None,
            initial=None,
            verbose_name=None,
            doc='',
            min=None,
            max=None,
            blank=False,
            null=True,
            help_text='',
            **kwargs):
                pass

    class TextField:
        pass


class widgets:
    def __getattr__(self, item):
        pass

    class HiddenInput: pass
    class CheckboxInput: pass
    class Select: pass
    class RadioSelect: pass
    class RadioSelectHorizontal: pass
    class SliderInput: pass
