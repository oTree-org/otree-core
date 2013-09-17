from django.contrib import admin
from donation.models import Match

# Treatment, Experiment, and Player are registered in ptree.admin
# So you don't need to register them here, unless you want to override their behavior.

class MatchAdmin(admin.ModelAdmin):
    readonly_fields = []

    # Match._meta.fields will display all fields on the match.
    list_display = readonly_fields + [f.name for f in Match._meta.fields]

admin.site.register(Match, MatchAdmin)