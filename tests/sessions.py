# -*- coding: utf-8 -*-

SESSION_TYPE_DEFAULTS = {
    'real_world_currency_per_point': 0.01,
    'participation_fee': 10.00,
    'num_bots': 12,
    'doc': "",
    'group_by_arrival_time': False,
}

session_types = [
    {
        'name': 'simple_game',
        'display_name': "Simple Game",
        'num_demo_participants': 1,
        'app_sequence': ['tests.simple_game'],
        'doc': ""
    },
    {
        "name": 'two_simple_games',
        "display_name": "2 Simple Games",
        "num_demo_participants": 1,
        "app_sequence": ['tests.simple_game', 'tests.simple_game_copy'],
        "doc": ""
    }
]


DEMO_PAGE_INTRO_TEXT = """
<ul>
    <li>
        <a href="https://github.com/oTree-org/otree" target="_blank">
            Source code
        </a>
        for the below games.
    </li>
    <li>
        <a href="http://www.otree.org/" target="_blank">oTree homepage</a>.
    </li>
</ul>
<p>
    Below are various games implemented with oTree. These games are all open
    source, and you can modify them as you wish to create your own variations.
    Click one to learn more and play.
</p>
"""
