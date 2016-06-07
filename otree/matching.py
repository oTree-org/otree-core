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
import random

from six.moves import map

# =============================================================================
# MATCH
# =============================================================================

def by_rank(ranked_list, players_per_group):
    ppg = players_per_group
    players = ranked_list
    group_matrix = []
    for i in range(0, len(players), ppg):
        group_matrix.append(players[i:i + ppg])
    return group_matrix


def randomly(group_matrix, fixed_id_in_group=False):
    """Random Uniform distribution of players in every group"""

    players = list(itertools.chain.from_iterable(group_matrix))
    sizes = [len(group) for group in group_matrix]
    if sizes and any(size != sizes[0] for size in sizes):
        raise ValueError(
            'This algorithm does not work with unevenly sized groups'
        )
    players_per_group = sizes[0]

    if fixed_id_in_group:
        group_matrix = [list(col) for col in zip(*group_matrix)]
        for column in group_matrix:
            random.shuffle(column)
        return list(zip(*group_matrix))
    else:
        random.shuffle(players)
        return by_rank(players, players_per_group)


def round_robin(subssn):
    """Try to generate every group of players with a lesser probabilty to mix
    the same players twice.

    **Warning:** This is slow, really slow. Seriously, it is very slow.

    """

    def pxg2id(players):
        participant_ids = [player.participant_id for player in players]
        participant_ids.sort()
        return "|".join(map(str, participant_ids))

    def usage_counts(subssn):
        counts = {}
        for p_subssn in subssn.in_previous_rounds():
            for players in p_subssn.get_group_matrix():
                size = len(players)
                if size not in counts:
                    counts[size] = collections.defaultdict(int)
                pxg_id = pxg2id(players)
                counts[size][pxg_id] += 1
        return counts

    def combinations_by_sizes(groups, players, counts):
        sizes, combinations = [], {}
        for group in groups:
            size = len(group)
            sizes.append(size)
            if size not in combinations:
                combs = []
                for players in itertools.combinations(players, size):
                    pxg_id = pxg2id(players)
                    count = counts[size][pxg_id]
                    combs.append((count, players))
                combs.sort(key=lambda e: e[0])
                combinations[size] = [comb[1] for comb in combs]
        return tuple(sizes), combinations

    def shuffle_sizes(sizes):
        ssizes = list(sizes)
        random.shuffle(ssizes)
        return ssizes

    def create_groups(sizes, combinations):
        groups = []
        used_participants = set()
        for size in sizes:
            comb, end, candidate = combinations[size], False, None
            while comb and not end:
                candidate = comb.pop(0)
                participant_ids = [p.participant_id for p in candidate]
                if not used_participants.intersection(participant_ids):
                    used_participants.update(participant_ids)
                    end = True
            groups.append(candidate)
        return groups

    def sort_by_sizes(groups, sizes):
        by_sizes = collections.defaultdict(list)
        for group in groups:
            by_sizes[len(group)].append(group)
        sorted_groups = [by_sizes[size].pop() for size in sizes]
        return sorted_groups

    groups = subssn.get_group_matrix()
    players = tuple(itertools.chain.from_iterable(groups))

    counts = usage_counts(subssn)
    sizes, combinations = combinations_by_sizes(groups, players, counts)
    ssizes = shuffle_sizes(sizes)
    shuffled_groups = create_groups(ssizes, combinations)
    groups = sort_by_sizes(shuffled_groups, sizes)
    return tuple(groups)


