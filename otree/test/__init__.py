#!/usr/bin/env python
# -*- coding: utf-8 -*-

# =============================================================================
# DOC
# =============================================================================

"""OTree test framework

"""

# NOTE: this imports the following submodules and then subclasses several
# classes importing is done via import_module rather than an ordinary import.
#
# The only reason for this is to hide the base classes from IDEs like PyCharm,
# so that those members/attributes don't show up in autocomplete,
# including all the built-in django fields that an ordinary oTree programmer
# will never need or want. if this was a conventional Django project I wouldn't
# do it this way, but because oTree is aimed at newcomers who may need more
# assistance from their IDE, I want to try this approach out.
#
# This module is also a form of documentation of the public API.

# =============================================================================
# IMPORTS
# =============================================================================

from importlib import import_module

client = import_module('otree.test.client')


# =============================================================================
# CLIENTS
# =============================================================================

class Bot(client.PlayerBot):

    def submit(self, ViewClass, param_dict=None):
        return super(Bot, self).submit(ViewClass, param_dict)

    def submit_invalid(self, ViewClass, param_dict=None):
        return super(Bot, self).submit_invalid(
            ViewClass, param_dict
        )
