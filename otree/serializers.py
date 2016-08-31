#!/usr/bin/env python
# encoding: utf-8

from otree.export import get_results_table_column_names
from rest_framework import serializers
from otree.models import Participant


class ParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Participant
        fields = get_results_table_column_names(Participant)
