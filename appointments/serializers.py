from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from appointments.models import Appointment, ConsultationRecord, PrescriptionItem
from appointments.services import book_appointment
from slots.models import Slot


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
    requested_tests = serializers.SerializerMethodField()

    class Meta:
        model = ConsultationRecord
        fields = ["diagnosis", "notes", "requested_tests", "prescription_items"]

    def get_requested_tests(self, obj: ConsultationRecord) -> list[str]:
        if not obj.requested_tests:
            return []
        return [item for item in obj.requested_tests.split("\n") if item]


class AppointmentBookingSerializer(serializers.Serializer):
    slot_id = serializers.IntegerField(required=False)
    doctor_id = serializers.IntegerField(required=False)
    appointment_date = serializers.DateField(required=False)
    appointment_time = serializers.TimeField(required=False)
    date = serializers.DateField(required=False)
    time = serializers.TimeField(required=False)
    reason = serializers.CharField(required=False, allow_blank=True)
    session_duration_minutes = serializers.IntegerField(required=False, min_value=1, default=30)

    def validate(self, attrs: dict) -> dict:
        if attrs.get("appointment_date") is None and attrs.get("date") is not None:
            attrs["appointment_date"] = attrs["date"]
        if attrs.get("appointment_time") is None and attrs.get("time") is not None:
            attrs["appointment_time"] = attrs["time"]
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

    def create(self, validated_data: dict) -> Appointment:
        validated_data.pop("date", None)
        validated_data.pop("time", None)
        patient = validated_data.pop("patient")
        return book_appointment(patient=patient, **validated_data)


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
            "reason",
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


class DoctorSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Slot
        fields = ["id", "date", "start_time", "end_time", "duration_minutes", "is_available"]


class DoctorQueueItemSerializer(serializers.ModelSerializer):
    patient_full_name = serializers.SerializerMethodField()
    waiting_time_minutes = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            "id",
            "patient_full_name",
            "appointment_time",
            "status",
            "check_in_time",
            "waiting_time_minutes",
        ]

    def get_patient_full_name(self, obj: Appointment) -> str:
        return f"{obj.patient.first_name} {obj.patient.last_name}".strip()

    def get_waiting_time_minutes(self, obj: Appointment) -> int | None:
        if obj.status != "CHECKED_IN" or not obj.check_in_time:
            return None
        delta = timezone.now() - obj.check_in_time
        return int(delta.total_seconds() // 60)


class PrescriptionItemInputSerializer(serializers.Serializer):
    drug = serializers.CharField()
    dose = serializers.CharField()
    duration = serializers.CharField()
    instructions = serializers.CharField(required=False, allow_blank=True)


class ConsultationCreateSerializer(serializers.Serializer):
    diagnosis = serializers.CharField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    requested_tests = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
    )
    prescription_items = PrescriptionItemInputSerializer(many=True, required=False, default=list)


class AvailableSlotSerializer(serializers.Serializer):
    doctorId = serializers.IntegerField()
    date = serializers.DateField()
    startTime = serializers.TimeField()
    endTime = serializers.TimeField()
