#!/usr/bin/env python
# encoding: utf-8

from otree.models.session import Session
from rest_framework import generics, permissions
from otree.serializers import ParticipantSerializer


class SessionParticipantsList(generics.ListCreateAPIView):
    serializer_class = ParticipantSerializer
    permission_classes = [
        permissions.AllowAny
    ]

    def get_queryset(self):
        session_code = self.kwargs['session_code']
        return Session.objects.get(code=session_code).get_participants()
