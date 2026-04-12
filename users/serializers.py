from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.contrib.auth import authenticate, get_user_model, password_validation
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings as jwt_api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import User
from users.permissions import IsApproved

@dataclass(frozen=True)
class TokenPair:
    access: str
    refresh: str


class TokenRefreshRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField(help_text="Valid refresh token.")


class TokenRefreshResponseSerializer(serializers.Serializer):
    access = serializers.CharField(help_text="New access token.")
    refresh = serializers.CharField(
        required=False,
        help_text="New refresh token when token rotation is enabled.",
    )


class MessageResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()

class SignupSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(
        choices=["patient", "doctor", "receptionist"],
        write_only=True,
        help_text="User role to assign at signup.",
    )
    password = serializers.CharField(write_only=True, min_length=6, help_text="Account password.")

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "first_name",
            "last_name",
            "phone_number",
            "date_of_birth",
            "role",
        ]

    def validate_date_of_birth(self, value: date) -> date:
        if value >= date.today():
            raise serializers.ValidationError("dateOfBirth must be in the past.")
        return value

    def validate_password(self, value: str) -> str:
        try:
            password_validation.validate_password(value)
        except DjangoValidationError as err:
            raise serializers.ValidationError(list(err.messages)) from err
        return value

    def create(self, validated_data: dict) -> User:
        role: str = validated_data.pop("role")
        password: str = validated_data.pop("password")
        is_approved: bool = role == "patient"
        user: User = User.objects.create_user(password=password, is_approved=is_approved, **validated_data)
        group_name: str = role.capitalize()
        group: Group = Group.objects.get(name=group_name)
        user.groups.add(group)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(help_text="Registered email address.")
    password = serializers.CharField(write_only=True, help_text="Account password.")

    def validate(self, attrs: dict) -> dict:
        email: str = attrs["email"]
        password: str = attrs["password"]
        user = authenticate(email=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")
        self.authenticated_user = user
        if not IsApproved.may_receive_tokens(user):
            raise PermissionDenied(detail=IsApproved.message)
        refresh = RefreshToken.for_user(user)
        return {
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
        }


class UserMeSerializer(serializers.ModelSerializer):
    groups = serializers.SerializerMethodField()

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
        ]

    def get_groups(self, obj: User) -> list[str]:
        return list(obj.groups.values_list("name", flat=True))


class SignupResponseSerializer(serializers.Serializer):
    user = UserMeSerializer()
    access_token = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Present when the account may receive JWTs",
    )
    refresh_token = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Present when the account may receive JWTs",
    )
    detail = serializers.CharField(
        required=False,
        help_text="Present when signup succeeded but JWTs are withheld pending approval.",
    )
    is_approved = serializers.BooleanField(
        required=False,
        help_text="False when doctor/receptionist must wait for admin approval.",
    )


class ApprovalAwareTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs: dict) -> dict:
        refresh = self.token_class(attrs["refresh"])
        user_id = refresh.payload.get(jwt_api_settings.USER_ID_CLAIM, None)
        if user_id is not None:
            user = get_user_model().objects.get(
                **{jwt_api_settings.USER_ID_FIELD: user_id}
            )
            if not IsApproved.may_receive_tokens(user):
                raise PermissionDenied(detail=IsApproved.message)
        return super().validate(attrs)


class LoginResponseSerializer(serializers.Serializer):
    user = UserMeSerializer()
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()


class LogoutRequestSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(help_text="Refresh token to blacklist.")

