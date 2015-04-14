#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Multiple algorithms for sorting oTree players

"""

# =============================================================================
# IMPORTS
# =============================================================================

import functools


# =============================================================================
# CONSTANTS
# =============================================================================

MATCHS = {}


# =============================================================================
# DECORATOR
# =============================================================================

def match_func(*names):

    def _wrap(func):

        @functools.wraps(func)
        def _dec(subssn):
            if subssn.round_number == 1:
                return extract_players(subssn)
            return func(subssn)

        for name in names:
            MATCHS[name] = _dec
        return _dec

    return _wrap


# =============================================================================
# MATCHS
# =============================================================================

def extract_players(subssn):
    return tuple(g.get_players() for g in subssn.get_groups())

@match_func("perfect_strangers", "round_robin")
def perfect_strangers(subssn):

    import ipdb; ipdb.set_trace()


@match_func("partners")
def partners(subssn):
    p_subssn = subssn.in_previous_rounds().last()
    return extract_players(p_subssn)


@match_func("swap_25")
def swap_25(subssn):
    pass


@match_func("reversed")
def reversed(subssn):
    p_subssn = subssn.in_previous_rounds().last()
    last_group = extract_players(p_subssn)
    return tuple(reversed(last_group))





