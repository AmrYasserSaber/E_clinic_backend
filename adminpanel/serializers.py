from __future__ import annotations

import logging

from django.contrib.auth.models import Group
from rest_framework import serializers

from users.models import User
from users.password_otp import generate_and_store_otp, otp_ttl_seconds
from users.welcome_email import send_admin_created_user_otp_email, send_profile_updated_email

logger = logging.getLogger(__name__)


ROLE_TO_GROUP = {
    "admin": "Admin",
    "doctor": "Doctor",
    "receptionist": "Receptionist",
    "patient": "Patient",
}

FIELD_LABELS: dict[str, str] = {
    "first_name": "First Name",
    "last_name": "Last Name",
    "email": "Email",
    "phone_number": "Phone Number",
    "specialty": "Specialty",
    "date_of_birth": "Date of Birth",
    "is_active": "Account Active",
    "is_approved": "Approved",
    "role": "Role",
}


class RoleFieldMixin:
    role = serializers.SerializerMethodField(read_only=True)

    def get_role(self, obj: User) -> str | None:
        first_group = obj.groups.first()
        return first_group.name.lower() if first_group else None


class AdminUserListSerializer(RoleFieldMixin, serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "specialty",
            "date_of_birth",
            "is_active",
            "is_approved",
            "role",
        ]


class AdminUserCreateSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(
        choices=list(ROLE_TO_GROUP.keys()),
        write_only=True,
        help_text="Maps to a Django auth group (Admin, Doctor, Receptionist, Patient).",
    )
    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "specialty",
            "date_of_birth",
            "is_active",
            "is_approved",
            "role",
        ]

    def validate_email(self, value: str) -> str:
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data: dict) -> User:
        role = validated_data.pop("role")
        user = User.objects.create_user(**validated_data)

        group = Group.objects.get(name=ROLE_TO_GROUP[role])
        user.groups.set([group])

        if role == "patient" and not user.is_approved:
            user.is_approved = True
            user.save(update_fields=["is_approved"])

        try:
            otp = generate_and_store_otp(user.email)
            send_admin_created_user_otp_email(
                user=user,
                otp=otp,
                expires_in_minutes=max(1, otp_ttl_seconds() // 60),
            )
        except Exception:
            logger.exception("Failed to send OTP email for admin-created user %s", user.pk)

        return user

    def to_representation(self, instance: User) -> dict:
        return AdminUserListSerializer(instance, context=self.context).data


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(
        choices=list(ROLE_TO_GROUP.keys()),
        required=False,
        write_only=True,
    )

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "specialty",
            "date_of_birth",
            "is_active",
            "is_approved",
            "role",
        ]

    def validate_email(self, value: str) -> str:
        user_id = self.instance.id if self.instance else None
        if User.objects.exclude(id=user_id).filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def update(self, instance: User, validated_data: dict) -> User:
        role = validated_data.pop("role", None)

        tracked_fields = [f for f in validated_data if f in FIELD_LABELS]
        old_values: dict[str, object] = {f: getattr(instance, f) for f in tracked_fields}

        old_group = instance.groups.first()
        old_role = old_group.name if old_group else None

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if role:
            group = Group.objects.get(name=ROLE_TO_GROUP[role])
            instance.groups.set([group])
            if role == "patient" and not instance.is_approved:
                instance.is_approved = True
                instance.save(update_fields=["is_approved"])

        def _display(field: str, val: object) -> str:
            if isinstance(val, bool):
                return "Yes" if val else "No"
            return str(val) if val not in (None, "") else "—"

        changes: list[dict[str, str]] = []
        for field in tracked_fields:
            new_val = getattr(instance, field)
            if old_values[field] != new_val:
                changes.append({
                    "field": FIELD_LABELS.get(field, field),
                    "old_value": _display(field, old_values[field]),
                    "new_value": _display(field, new_val),
                })

        new_role = ROLE_TO_GROUP.get(role) if role else None
        if new_role and new_role != old_role:
            changes.append({
                "field": FIELD_LABELS["role"],
                "old_value": old_role or "—",
                "new_value": new_role,
            })

        is_approval = (
            "is_approved" in old_values
            and not old_values["is_approved"]
            and instance.is_approved
        )

        send_profile_updated_email(
            user=instance,
            changes=changes,
            is_approval=is_approval,
        )

        return instance

    def to_representation(self, instance: User) -> dict:
        return AdminUserListSerializer(instance, context=self.context).data


class PatientListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "date_of_birth",
            "is_active",
        ]