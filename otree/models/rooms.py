from django.contrib.auth.models import User
from otree.db import models
from django.db import models as djmodels


class Rooms(models.Model):
    """Rooms models class for creating rooms"""

    class Meta:
        ordering = ['pk']

    room_name = models.StringField(max_length=100)
    teacher = djmodels.ForeignKey(User, db_column="user", on_delete=models.CASCADE)
