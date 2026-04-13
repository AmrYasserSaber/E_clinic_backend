from __future__ import annotations

from rest_framework import serializers


class QueueQuerySerializer(serializers.Serializer):
    date = serializers.CharField(required=False)
    doctor_id = serializers.IntegerField(required=False, min_value=1)


class QueueItemSerializer(serializers.Serializer):
    queue_position = serializers.IntegerField()
    waiting_time = serializers.IntegerField(help_text="Waiting time in minutes")
    patient_name = serializers.CharField()
    doctor_name = serializers.CharField()
    appointment_id = serializers.IntegerField()
    doctor_id = serializers.IntegerField()
    date = serializers.DateField()
    time = serializers.TimeField()
    status = serializers.CharField()
    check_in_time = serializers.DateTimeField(allow_null=True)


class DoctorAvailabilitySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    specialty = serializers.CharField()
    status = serializers.ChoiceField(choices=["AVAILABLE", "BUSY", "AWAY"])
