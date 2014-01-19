__doc__ = """See https://docs.djangoproject.com/en/dev/ref/contrib/admin/"""

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.models import Group
from data_exports.models import Export, Format
from data_exports.admin import ExportAdmin
import ptree.adminlib
import ptree.session.models

admin.site.register(ptree.session.models.Session,
                    ptree.adminlib.SessionAdmin
                    )

admin.site.register(ptree.session.models.SessionParticipant,
                    ptree.adminlib.SessionParticipantAdmin)

admin.site.unregister(Export)

# users don't need to see this
admin.site.unregister(Format)

class PTreeExportAdmin(ExportAdmin):

    # In Django 1.7, I can set list_display_links to None and then put 'name' first
    list_display = ['get_export_link', 'name']
    ordering = ['slug']
    list_filter = []


admin.site.register(Export, PTreeExportAdmin)

admin.site.unregister(User)
admin.site.unregister(Group)
