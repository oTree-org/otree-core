#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# CONSTANTS and confs
# =============================================================================

# start patch releases at .10, not .0 or .1,
# because then alphabetical ordering will match lexical ordering
# e.g. users might think that 0.4.5 is newer than 0.4.49
VERSION = ('0', '4', '10')

__version__ = ".".join(VERSION)

default_app_config = 'otree.apps.OtreeConfig'


# =============================================================================
# FUNCTIONS
# =============================================================================

def get_version():
    return __version__
