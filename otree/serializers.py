#!/usr/bin/env python
# encoding: utf-8

from rest_framework import serializers
from otree.models.participant import Participant


class ParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Participant
        fields = [
            '_id_in_session',
            'code',
            'label',
            '_current_page',
            '_current_app_name',
            '_round_number',
            '_current_page_name',
            'status',
            'last_request_succeeded',
            '_last_page_timestamp',
        ]
