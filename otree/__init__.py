# setup.py imports this module, so this module must not import django
# or any other 3rd party packages.
__version__ = '3.0.1'
default_app_config = 'otree.apps.OtreeConfig'
