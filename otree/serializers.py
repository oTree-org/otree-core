#!/usr/bin/env python
# encoding: utf-8

from otree.export import get_field_names_for_live_update
from rest_framework import serializers
from otree.models import Participant


class ParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Participant
        fields = get_field_names_for_live_update(Participant)
