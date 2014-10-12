__doc__ = """See https://docs.djangoproject.com/en/dev/ref/contrib/admin/"""

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.models import Group

import otree.adminlib
import otree.sessionlib.models


admin.site.register(otree.sessionlib.models.GlobalSettings, otree.adminlib.GlobalSettingsAdmin)

admin.site.register(otree.sessionlib.models.Session,
                    otree.adminlib.SessionAdmin
                    )

admin.site.register(otree.sessionlib.models.Participant,
                    otree.adminlib.ParticipantAdmin)

admin.site.unregister(User)
admin.site.unregister(Group)
