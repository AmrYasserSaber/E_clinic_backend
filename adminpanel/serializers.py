from __future__ import annotations

from django.contrib.auth.models import Group
from rest_framework import serializers

from users.models import User


ROLE_TO_GROUP = {
    "admin": "Admin",
    "doctor": "Doctor",
    "receptionist": "Receptionist",
    "patient": "Patient",
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
            "date_of_birth",
            "is_active",
            "is_approved",
            "role",
        ]


class AdminUserCreateSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=list(ROLE_TO_GROUP.keys()))
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "first_name",
            "last_name",
            "phone_number",
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
        password = validated_data.pop("password", "TempPass123")
        user = User.objects.create_user(password=password, **validated_data)

        group = Group.objects.get(name=ROLE_TO_GROUP[role])
        user.groups.set([group])

        if role == "patient" and not user.is_approved:
            user.is_approved = True
            user.save(update_fields=["is_approved"])

        return user


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=list(ROLE_TO_GROUP.keys()), required=False)

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone_number",
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

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if role:
            group = Group.objects.get(name=ROLE_TO_GROUP[role])
            instance.groups.set([group])

        return instance


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