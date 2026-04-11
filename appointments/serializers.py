from __future__ import annotations

from rest_framework import serializers


class AvailableSlotSerializer(serializers.Serializer):
    doctorId = serializers.IntegerField()
    date = serializers.DateField()
    startTime = serializers.TimeField()
    endTime = serializers.TimeField()
