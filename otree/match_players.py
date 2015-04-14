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
                return players_x_groups(subssn)
            return func(subssn)

        for name in names:
            MATCHS[name] = _dec
        return _dec

    return _wrap


# =============================================================================
# MATCHS
# =============================================================================

def players_x_groups(subssn):
    return tuple(g.get_players() for g in subssn.get_groups())


@match_func("perfect_strangers", "round_robin")
def perfect_strangers(subssn):

    import ipdb; ipdb.set_trace()


@match_func("partners")
def partners(subssn):
    p_subssn = subssn.in_previous_rounds()[-1]
    return players_x_groups(p_subssn)


@match_func("swap_25")
def swap_25(subssn):
    pass


@match_func("reversed")
def players_reversed(subssn):
    p_subssn = subssn.in_previous_rounds()[-1]
    reversed_players_x_groups = []
    for players in players_x_groups(p_subssn):
        players_reversed = list(reversed(players))
        reversed_players_x_groups.append(players_reversed)
    return tuple(reversed_players_x_groups)



