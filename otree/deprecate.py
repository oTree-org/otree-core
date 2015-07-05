#!/usr/bin/env python
# -*- coding: utf-8 -*-


import functools
import warnings

from django.conf import settings


# =============================================================================
# CONSTANTS
# =============================================================================

OTREE_DEPRECATION_WARNING = getattr(
    settings, "OTREE_DEPRECATION_WARNING", "default")

MSG_TPL = "Call to deprecated function '{name}'."

MSG_ALTERNATIVE_TPL = (
    "Call to deprecated function '{name}'. Instead please use '{alternative}'")


# =============================================================================
# DEPRECATED CLASS
# =============================================================================

class OTreeDeprecationWarning(DeprecationWarning):
    pass


# =============================================================================
# FUNCTIONS
# =============================================================================

def dmessage(func, alternative=None):
    """Create a simple deprecation message for a function

    """
    name = func.__name__
    template = MSG_TPL if alternative is None else MSG_ALTERNATIVE_TPL
    return template.format(name=name, alternative=alternative)


def deprecated(alternative=None):
    """Mark deprecated functions with this decorator.

    Params
    ------

    alternative: None or str
        Show which is the alternative to this call

    .. warning::

        Use it as the closest one to the function you decorate.

    """

    def _decorator(func):

        msg = dmessage(func, alternative)

        @functools.wraps(func)
        def _wraps(*args, **kwargs):
            dwarning(msg)
            return func(*args, **kwargs)
        return _wraps

    return _decorator


def dwarning(msg):
    """Show a oTree deprecation warning with the given message"""
    warnings.warn(msg, OTreeDeprecationWarning, stacklevel=2)


# =============================================================================
# CONFIGURATIONS
# =============================================================================

warnings.simplefilter(OTREE_DEPRECATION_WARNING, OTreeDeprecationWarning)
