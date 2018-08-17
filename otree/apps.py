#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import sys

import colorama
from django.apps import AppConfig
from django.conf import settings
from django.db.models import signals

import otree
import otree.common_internal
from otree.common_internal import (
    ensure_superuser_exists
)
from otree.strict_templates import patch_template_silent_failures


logger = logging.getLogger('otree')


def create_singleton_objects(sender, **kwargs):
    from otree.models_concrete import UndefinedFormModel
    for ModelClass in [UndefinedFormModel]:
        # if it doesn't already exist, create one.
        ModelClass.objects.get_or_create()


def monkey_patch_static_tag():
    '''
    In Django >= 1.10, you can use {% load static %}
    instead of {% load staticfiles %}. if we switch to that format,
    then it will bypass this. so eventually after Django 1.10, we
    should change this code to patch django.templatetags.static.static
    '''

    from django.contrib.staticfiles.storage import staticfiles_storage
    from django.contrib.staticfiles.templatetags import staticfiles

    def patched_static(path):
        '''same 1-line function,
        just tries to give a friendlier error message'''
        try:
            return staticfiles_storage.url(path)
        except ValueError as exc:
            # Heroku and "otree runprodserver" both execute collectstatic
            # automatically, so there is ordinarily no need to suggest
            # running collectstatic if a file is not found. It's more likely
            # that the file doesn't exist or wasn't added in git.
            if 'runserver' in sys.argv or 'devserver' in sys.argv:
                msg = '{} - did you remember to run "otree collectstatic"?'
                raise ValueError(msg.format(exc)) from None
            else:
                raise exc from None


    staticfiles.static = patched_static


SQLITE_LOCKING_ADVICE = (
    'Locking is common with SQLite. '
    'When you run your study, you should use a database like PostgreSQL '
    'that is resistant to locking'
)


def monkey_patch_db_cursor():
    '''Monkey-patch the DB cursor, to catch ProgrammingError and
    OperationalError. The alternative is to use middleware, but (1)
    that doesn't catch errors raised outside of views, like channels consumers
    and the task queue, and (2) it's not as specific, because there are
    OperationalErrors that come from different parts of the app that are
    unrelated to resetdb. This is the most targeted location.
    '''


    # In Django 2.0, this method is renamed to _execute.
    def execute(self, sql, params=None):
        self.db.validate_no_broken_transaction()
        with self.db.wrap_database_errors:
            if params is None:
                return self.cursor.execute(sql)
            else:
                try:
                    return self.cursor.execute(sql, params)
                except Exception as exc:
                    ExceptionClass = type(exc)
                    # it seems there are different exceptions all named
                    # OperationalError (django.db.OperationalError,
                    # sqlite.OperationalError, mysql....)
                    # so, simplest to use the string name
                    if ExceptionClass.__name__ in (
                            'OperationalError', 'ProgrammingError'):
                        # these error messages are localized, so we can't
                        # just check for substring 'column' or 'table'
                        # all the ProgrammingError and OperationalError
                        # instances I've seen so far are related to resetdb,
                        # except for "database is locked"
                        tb = sys.exc_info()[2]

                        if 'locked' in str(exc):
                            advice = SQLITE_LOCKING_ADVICE
                        else:
                            advice = 'try running "otree resetdb"'

                        raise ExceptionClass('{} - {}.'.format(
                            exc, advice)).with_traceback(tb) from None
                    else:
                        raise

    from django.db.backends import utils
    utils.CursorWrapper.execute = execute


def setup_create_default_superuser():
    signals.post_migrate.connect(
        ensure_superuser_exists,
        dispatch_uid='otree.create_superuser'
    )


def setup_create_singleton_objects():
    signals.post_migrate.connect(create_singleton_objects,
                                 dispatch_uid='create_singletons')


def patch_raven_config():
    # patch settings with info that is only available
    # after other settings loaded
    if hasattr(settings, 'RAVEN_CONFIG'):
        settings.RAVEN_CONFIG['release'] = '{}{}'.format(
            otree.__version__,
            # need to pass the server if it's DEBUG
            # mode. could do this in extra context or tags,
            # but this seems the most straightforward way
            ',dbg' if settings.DEBUG else ''
        )


class OtreeConfig(AppConfig):
    name = 'otree'
    label = 'otree'
    verbose_name = "oTree"

    def ready(self):
        setup_create_singleton_objects()
        setup_create_default_superuser()
        patch_raven_config()
        monkey_patch_static_tag()
        monkey_patch_db_cursor()
        # to initialize locks

        colorama.init(autoreset=True)

        import otree.checks
        otree.checks.register_system_checks()
        patch_template_silent_failures()


