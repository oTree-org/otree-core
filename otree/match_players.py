#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Multiple algorithms for sorting oTree players

"""

# =============================================================================
# IMPORTS
# =============================================================================

import functools
import itertools
import collections


# =============================================================================
# CONSTANTS
# =============================================================================

MATCHS = {}


# =============================================================================
# DECORATOR
# =============================================================================

def match_func(*names):
    """Register a matching function with diferent aliases

    Example:

    ::

        @match_func("fancy_name", "ugly_name")
        def matching_function(subssn):
            ...

    Then you can use this this function in you ``before_session_starts`` method
    as:

    ::

        def before_session_starts(self):
            self.match_players("fancy_name")

    or

    ::

        def before_session_starts(self):
            self.match_players("ugly_name")

    """
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
    """Conver a subssn in a tuple of list of players

    """
    return tuple(g.get_players() for g in subssn.get_groups())


# =============================================================================
# MATCH
# =============================================================================

@match_func("perfect_strangers", "round_robin")
def round_robin(subssn):
    """Try to generate every group of players with a lesser probabilty to mixe
    the same players twice

    """
    # all available players
    all_players = tuple(
        itertools.chain.from_iterable(players_x_groups(subssn)))

    def intersect_any(players, already_choiced):
        """Return true if players groups already exists in any already_choiced
        list of groups

        """
        players_set = frozenset(players_ids(players))
        all_ready_choiced = map(
            players_ids,
            [plys for plys in already_choiced if len(plys) == len(players)])
        return any(map(players_set.intersection, already_choiced))

    def players_ids(players):
        """Generate a unique id as tuple for a group of players"""
        return tuple(sorted(ply.participant_id for ply in players))

    # first retrieve all existing groups count in prev rounds groped by size
    prev_round_buff = collections.defaultdict(
        lambda: collections.defaultdict(int))
    for p_subssn in subssn.in_previous_rounds():
        for players in players_x_groups(p_subssn):
            size, ply_ids = len(players), players_ids(players)
            prev_round_buff[size][ply_ids] += 1

    # this is subroutine for select the less frequent group
    prev_round_lfreq = {}  # lesser frequency for a given size
    prev_round_lfreq_players = {}  # the players with the lfreq for given size
    def get_less_frequent(players, size, already_choiced):
        """Get the most infrequent combintation of players"""
        for comb in itertools.combinations(players, size):
            if not intersect_any(players, already_choiced):
                ply_ids = players_ids(comb)
                freq = prev_round_buff[size][ply_ids]
                if freq == 0:
                    return players
                elif size not in prev_round_lfreq:
                    prev_round_lfreq[size] = freq
                    prev_round_lfreq_players[size] = comb
                elif freq < prev_round_lfreq[size]:
                    prev_round_lfreq[size] = freq
                    prev_round_lfreq_players[size] = comb

        return prev_round_lfreq_players[size]

    groups = []
    for ppg in subssn._get_players_per_group_list():
        groups.append(get_less_frequent(all_players, ppg, groups))

    return tuple(groups)


@match_func("partners")
def partners(subssn):
    """Every player go with the same player in every round"""
    return players_x_groups(subssn)


@match_func("reversed", "players_reversed")
def players_reversed(subssn):
    """Change the order of a players ina group. In a even group the central
    player never change

    """
    def reverse_group(g):
        return list(reversed(g))

    p_subssn = players_x_groups(subssn)
    rev_p = map(reverse_group, p_subssn)

    return tuple(rev_p)

