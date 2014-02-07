__doc__ = """See https://docs.djangoproject.com/en/dev/ref/contrib/admin/"""

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.models import Group
import ptree.adminlib
import ptree.session.models

admin.site.register(ptree.session.models.Session,
                    ptree.adminlib.SessionAdmin
                    )

admin.site.register(ptree.session.models.SessionParticipant,
                    ptree.adminlib.SessionParticipantAdmin)

admin.site.unregister(User)
admin.site.unregister(Group)
