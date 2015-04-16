#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Multiple algorithms for sorting oTree players

"""

# =============================================================================
# IMPORTS
# =============================================================================

import collections
import functools
import itertools


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

    def gen_pxg_id(pxg):
        groups = []
        for players in pxg:
            ply_ids = [ply.id for ply in players]
            ply_ids.sort()
            groups.append(tuple(ply_ids))
        groups.sort()
        groups_str = [",".join(map(str, g)) for g in groups]
        return "|".join(groups_str)

    def chunkify(lst, n):
        return [lst[i::n] for i in xrange(n)]

    def roundrobin(*iterables):
        "roundrobin('ABC', 'D', 'EF') --> A D E B F C"
        # Recipe credited to George Sakkis
        pending = len(iterables)
        nexts = itertools.cycle(iter(it).next for it in iterables)
        while pending:
            try:
                for next in nexts:
                    yield next()
            except StopIteration:
                pending -= 1
                nexts = itertools.cycle(itertools.islice(nexts, pending))

    # retrieve all users groups
    used_groups = collections.defaultdict(int)
    for p_subssn in subssn.in_previous_rounds():
        pxg = players_x_groups(p_subssn)
        pxg_ids = gen_pxg_id(pxg)
        used_groups[pxg_ids] += 1


    players = tuple(itertools.chain.from_iterable(players_x_groups(subssn)))

    ppg = subssn._Constants.players_per_group

    chunked = chunkify(players, ppg)

    candidates = roundrobin(*chunked)

    import ipdb; ipdb.set_trace()


@match_func("partners")
def partners(subssn):
    p_subssn = subssn.in_previous_rounds()[-1]
    return players_x_groups(p_subssn)


@match_func("reversed", "players_reversed")
def players_reversed(subssn):
    p_subssn = subssn.in_previous_rounds()[-1]
    reversed_players_x_groups = []
    for players in players_x_groups(p_subssn):
        players_reversed = list(reversed(players))
        reversed_players_x_groups.append(players_reversed)
    return tuple(reversed_players_x_groups)



