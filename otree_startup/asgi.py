import os
import django
from channels.routing import get_default_application
from . import configure_settings
from django.conf import settings

# needed if uvicorn is launched multi-process
if not settings.configured:
    configure_settings()
    django.setup()

application = get_default_application()
