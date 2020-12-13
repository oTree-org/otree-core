# oTree seems to work fine without this monkeypatch. maybe because our command is called devserver, not runserver,
# so there is no ambiguity.
def monkeypatch_django():
    """
    Monkeypatches support for us into parts of Django.
    """
    # Ensure that the staticfiles version of runserver bows down to us
    # This one is particularly horrible
    from django.contrib.staticfiles.management.commands.runserver import (
        Command as StaticRunserverCommand,
    )
    from .management.commands.runserver import Command as RunserverCommand

    StaticRunserverCommand.__bases__ = (RunserverCommand,)
