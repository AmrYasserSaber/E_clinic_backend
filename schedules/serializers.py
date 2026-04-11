from __future__ import annotations

from rest_framework import serializers

from .models import DoctorSchedule, ScheduleException


class DoctorScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorSchedule
        fields = [
            "id",
            "doctor",
            "day_of_week",
            "start_time",
            "end_time",
            "session_duration_minutes",
            "buffer_minutes",
        ]
        read_only_fields = ["id", "doctor"]


class DoctorScheduleUpsertListSerializer(serializers.ListSerializer):
    def validate(self, attrs):
        day_values = [item["day_of_week"] for item in attrs]
        if len(day_values) != len(set(day_values)):
            raise serializers.ValidationError("Each day_of_week must appear only once in request body.")
        return attrs


class DoctorScheduleUpsertItemSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")
        if start_time and end_time and end_time <= start_time:
            raise serializers.ValidationError({"end_time": "end_time must be later than start_time."})
        return attrs

    class Meta:
        model = DoctorSchedule
        list_serializer_class = DoctorScheduleUpsertListSerializer
        fields = [
            "day_of_week",
            "start_time",
            "end_time",
            "session_duration_minutes",
            "buffer_minutes",
        ]


class DoctorScheduleDayUpdateSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        start_time = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end_time = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start_time and end_time and end_time <= start_time:
            raise serializers.ValidationError({"end_time": "end_time must be later than start_time."})
        return attrs

    class Meta:
        model = DoctorSchedule
        fields = [
            "start_time",
            "end_time",
            "session_duration_minutes",
            "buffer_minutes",
        ]


class ScheduleExceptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleException
        fields = [
            "id",
            "doctor",
            "start_date",
            "end_date",
            "exception_type",
            "custom_start_time",
            "custom_end_time",
            "reason",
        ]
        read_only_fields = ["id", "doctor"]


class ScheduleExceptionCreateSerializer(serializers.ModelSerializer):
    exception_type = serializers.ChoiceField(choices=ScheduleException.EXCEPTION_TYPE_CHOICES)

    class Meta:
        model = ScheduleException
        fields = [
            "start_date",
            "end_date",
            "exception_type",
            "custom_start_time",
            "custom_end_time",
            "reason",
        ]

    def validate(self, attrs):
        exception_type = attrs.get("exception_type")
        custom_start_time = attrs.get("custom_start_time")
        custom_end_time = attrs.get("custom_end_time")
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")

        if end_date and start_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "end_date cannot be earlier than start_date."})

        if exception_type == ScheduleException.EXCEPTION_DAY_OFF:
            if custom_start_time or custom_end_time:
                raise serializers.ValidationError(
                    "For day_off exception, custom_start_time and custom_end_time must be empty."
                )

        if exception_type == ScheduleException.EXCEPTION_ONE_OFF:
            if not custom_start_time or not custom_end_time:
                raise serializers.ValidationError(
                    "For one_off exception, custom_start_time and custom_end_time are required."
                )
            if custom_end_time <= custom_start_time:
                raise serializers.ValidationError(
                    {"custom_end_time": "custom_end_time must be later than custom_start_time."}
                )

        return attrs
