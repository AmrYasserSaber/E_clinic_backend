from __future__ import annotations

from datetime import date

from rest_framework import serializers

from patients.models import PatientProfile
from users.models import User


class PatientProfileReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientProfile
        fields = [
            "emergency_contact_name",
            "emergency_contact_phone",
            "address",
            "notes",
            "created_at",
            "updated_at",
        ]


class PatientMeReadSerializer(serializers.ModelSerializer):
    groups = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "date_of_birth",
            "groups",
            "profile",
        ]

    def get_groups(self, obj: User) -> list[str]:
        return list(obj.groups.values_list("name", flat=True))

    def get_profile(self, obj: User) -> dict | None:
        if not hasattr(obj, "patient_profile"):
            return None
        return PatientProfileReadSerializer(obj.patient_profile).data


class PatientUserPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone_number", "date_of_birth"]

    def validate_date_of_birth(self, value: date) -> date:
        if value >= date.today():
            raise serializers.ValidationError("dateOfBirth must be in the past.")
        return value


class PatientProfilePatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientProfile
        fields = [
            "emergency_contact_name",
            "emergency_contact_phone",
            "address",
            "notes",
        ]
