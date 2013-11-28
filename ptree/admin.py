__doc__ = """See https://docs.djangoproject.com/en/dev/ref/contrib/admin/"""

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.models import Group
from data_exports.models import Export
from data_exports.admin import ExportAdmin
import ptree.common
from ptree.sequence_of_experiments.models import SequenceOfExperiments

admin.site.register(SequenceOfExperiments, ptree.common.SequenceOfExperimentsAdmin)

admin.site.unregister(Export)

class PTreeExportAdmin(ExportAdmin):

    # In Django 1.7, I can set list_display_links to None and then put 'name' first
    list_display = ['get_export_link', 'name']
    ordering = ['slug']


admin.site.register(Export, PTreeExportAdmin)

admin.site.unregister(User)
admin.site.unregister(Group)
