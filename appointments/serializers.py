from __future__ import annotations

from rest_framework import serializers

from appointments.models import Appointment, ConsultationRecord, PrescriptionItem
from appointments.services import book_appointment


class PrescriptionItemReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrescriptionItem
        fields = ["id", "drug", "dose", "duration", "instructions"]


class ConsultationRecordReadSerializer(serializers.ModelSerializer):
    prescription_items = PrescriptionItemReadSerializer(many=True, read_only=True)

    class Meta:
        model = ConsultationRecord
        fields = ["diagnosis", "notes", "requested_tests", "prescription_items"]


class AppointmentBookingSerializer(serializers.Serializer):
    slot_id = serializers.IntegerField(required=False)
    doctor_id = serializers.IntegerField(required=False)
    appointment_date = serializers.DateField(required=False)
    appointment_time = serializers.TimeField(required=False)
    session_duration_minutes = serializers.IntegerField(required=False, min_value=1, default=30)

    def create(self, validated_data: dict) -> Appointment:
        patient = validated_data.pop("patient")
        return book_appointment(patient=patient, **validated_data)

    def validate(self, attrs: dict) -> dict:
        if attrs.get("slot_id") is None:
            missing_fields = [
                field_name
                for field_name in ["doctor_id", "appointment_date", "appointment_time"]
                if attrs.get(field_name) is None
            ]
            if missing_fields:
                missing_fields_str = ", ".join(missing_fields)
                raise serializers.ValidationError(
                    f"Missing required fields when slot_id is not provided: {missing_fields_str}."
                )
        return attrs


class AppointmentSerializer(serializers.ModelSerializer):
    consultation_summary = ConsultationRecordReadSerializer(source="consultation_record", read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "patient",
            "doctor",
            "slot",
            "appointment_date",
            "appointment_time",
            "session_duration_minutes",
            "status",
            "check_in_time",
            "consultation_summary",
            "created_at",
            "updated_at",
        ]
