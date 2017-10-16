#!/usr/bin/env python
# -*- coding: utf-8 -*-

# for py.test.
# this doesnt work if the module is under otree.bots, so i put it here
from otree.session import SESSION_CONFIGS_DICT


def pytest_addoption(parser):
    parser.addoption("--session_config_name")
    parser.addoption("--num_participants")
    parser.addoption("--export_path")
    parser.addoption("--preserve_data", action='store_true')


def pytest_generate_tests(metafunc):
    # if the test function has a parameter called session_config_name
    if 'session_config_name' in metafunc.fixturenames:
        option = metafunc.config.option
        session_config_name = option.session_config_name
        if session_config_name:
            session_config_names = [session_config_name]
        else:
            session_config_names = SESSION_CONFIGS_DICT.keys()
        num_participants = option.num_participants
        if num_participants:
            num_participants = int(num_participants)
        params = [
            [name, num_participants, False]
            for name in session_config_names]
        if option.preserve_data and len(params) >= 1:
            params[-1][2] = True
        metafunc.parametrize(
            "session_config_name,num_participants,run_export", params)
