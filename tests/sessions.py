# -*- coding: utf-8 -*-

import otree.session


class SessionType(otree.session.SessionType):

    # defaults that can be overridden by an individual SessionType below
    money_per_point = 1.00
    demo_enabled = True
    fixed_pay = 10.00
    num_bots = 12
    doc = "."
    group_by_arrival_order = False
    show_on_demo_page = True
    vars = {}


def session_types():
    return [
        SessionType(
            name="simple_game",
            display_name="Simple Game",
            num_demo_participants=1,
            subsession_apps=['tests.simple_game'],
            doc=""""""
        ),
        SessionType(
            name="two_simple_games",
            display_name="2 Simple Games",
            num_demo_participants=1,
            subsession_apps=['tests.simple_game', 'tests.simple_game_copy'],
            doc=""""""
        ),
    ]


demo_page_intro_text = """
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
