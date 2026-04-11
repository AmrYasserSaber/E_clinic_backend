from __future__ import annotations

from rest_framework import serializers

from appointments.models import Appointment, ConsultationRecord, PrescriptionItem
from appointments.services import book_appointment


class UserBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()


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


class BaseAppointmentSerializer(serializers.ModelSerializer):
    patient_info = UserBriefSerializer(source="patient", read_only=True)
    doctor_info = UserBriefSerializer(source="doctor", read_only=True)

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
            "patient_info",
            "doctor_info",
            "created_at",
            "updated_at",
        ]


class AppointmentSerializer(BaseAppointmentSerializer):
    consultation_summary = ConsultationRecordReadSerializer(source="consultation_record", read_only=True)

    class Meta:
        model = Appointment
        fields = BaseAppointmentSerializer.Meta.fields + ["consultation_summary"]


class ReceptionistAppointmentSerializer(BaseAppointmentSerializer):
    pass


class AppointmentDeclineSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)


class AppointmentRescheduleSerializer(serializers.Serializer):
    new_slot_id = serializers.IntegerField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True)
