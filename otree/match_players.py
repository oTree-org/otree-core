#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Multiple algorithms for sorting oTree players

"""

# =============================================================================
# IMPORTS
# =============================================================================

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

    def roundrobin(iterable, n):

        def norepeat(tail, buff):
            group = []
            if tail:
                sg, sub_tail = tuple(sorted(tail[0])), tail[1:]
                if not buff.intersection(sg):
                    buff.update(sg)
                    group.append(sg)
                group += norepeat(sub_tail, buff)
            return group

        subgroups = tuple(itertools.combinations(iterable, n))
        subgroups_len = len(subgroups)
        yielded = set()
        for idx in range(subgroups_len):
            sg = tuple(sorted(subgroups[idx]))
            tail = subgroups[:idx] + subgroups[idx + 1:]
            buff = set(sg)
            group = [sg] + norepeat(tail, buff)
            group = tuple(sorted(group))
            if group not in yielded:
                yielded.add(group)
                yield group

    # retrieve all users groups
    pxg_ids_cnt = {}
    pxg_ids_to_pxg = {}
    for p_subssn in subssn.in_previous_rounds():
        pxg = players_x_groups(p_subssn)
        pxg_ids = gen_pxg_id(pxg)
        if pxg_ids in pxg_ids_cnt:
            pxg_ids_cnt[pxg_ids] += 1
        else:
            pxg_ids_cnt[pxg_ids] = 1
            pxg_ids_to_pxg[pxg_ids] = pxg

    players = tuple(itertools.chain.from_iterable(players_x_groups(subssn)))

    ppg = subssn._Constants.players_per_group

    for pxg in roundrobin(players, ppg):
        pxg_ids = gen_pxg_id(pxg)
        if pxg_ids not in pxg_ids_cnt:
            return tuple(pxg)

    pxg_ids_cnt_items = pxg_ids_cnt.items()
    pxg_ids_cnt_items.sort(key=lambda e: e[1])

    key = pxg_ids_cnt_items[0][0]
    return tuple(pxg_ids_to_pxg[key])


@match_func("partners")
def partners(subssn):
    return players_x_groups(subssn)


@match_func("reversed", "players_reversed")
def players_reversed(subssn):

    def reverse_group(g):
        return list(reversed(g))

    p_subssn = players_x_groups(subssn)
    rev_p = map(reverse_group, p_subssn)

    return tuple(rev_p)

