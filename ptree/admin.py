__doc__ = """See https://docs.djangoproject.com/en/dev/ref/contrib/admin/"""

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.models import Group

import ptree.adminlib
import ptree.sessionlib.models


admin.site.register(ptree.sessionlib.models.Session,
                    ptree.adminlib.SessionAdmin
                    )

admin.site.register(ptree.sessionlib.models.SessionParticipant,
                    ptree.adminlib.SessionParticipantAdmin)

admin.site.unregister(User)
admin.site.unregister(Group)
