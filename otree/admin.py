__doc__ = """See https://docs.djangoproject.com/en/dev/ref/contrib/admin/"""

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.models import Group

import otree.adminlib
import otree.models.session


admin.site.register(otree.models.session.GlobalSingleton,
                    otree.adminlib.GlobalSingletonAdmin)
admin.site.register(otree.models.session.Session,
                    otree.adminlib.SessionAdmin)
admin.site.register(otree.models.session.Participant,
                    otree.adminlib.ParticipantAdmin)
admin.site.register(otree.models.session.ParticipantProxy,
                    otree.adminlib.MonitorParticipantAdmin)
admin.site.unregister(User)
admin.site.unregister(Group)
