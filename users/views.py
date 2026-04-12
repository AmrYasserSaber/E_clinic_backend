from __future__ import annotations

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema

from users.permissions import IsApproved
from users.serializers import (
    LoginResponseSerializer,
    LoginSerializer,
    LogoutRequestSerializer,
    MessageResponseSerializer,
    SignupResponseSerializer,
    SignupSerializer,
    UserMeSerializer,
)


class SignupView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Authentication"],
        summary="Create a new account",
        description=(
            "Registers a patient, doctor, or receptionist. Patients receive JWT tokens "
            "immediately; doctors and receptionists are created pending admin approval "
            "and do not receive tokens until approved."
        ),
        request=SignupSerializer,
        responses={201: SignupResponseSerializer, 400: MessageResponseSerializer},
    )
    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user_serializer = UserMeSerializer(user)
        if not IsApproved.may_receive_tokens(user):
            return Response(
                {
                    "user": user_serializer.data,
                    "detail": "Account created. Pending admin approval.",
                    "is_approved": False,
                },
                status=201,
            )
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": user_serializer.data,
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
            },
            status=201,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Authentication"],
        summary="Login",
        description=(
            "Authenticates credentials and returns JWT tokens when the account may "
            "receive them. Doctors and receptionists pending approval receive 403."
        ),
        request=LoginSerializer,
        responses={
            200: LoginResponseSerializer,
            400: MessageResponseSerializer,
            403: MessageResponseSerializer,
        },
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = getattr(serializer, "authenticated_user", None)
        user_serializer = UserMeSerializer(user)
        return Response(
            {
                "user": user_serializer.data,
                **serializer.validated_data,
            },
            status=200,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated, IsApproved]

    @extend_schema(
        tags=["Authentication"],
        summary="Logout",
        description="Blacklists a refresh token.",
        request=LogoutRequestSerializer,
        responses={
            204: None,
            400: MessageResponseSerializer,
        },
    )
    def post(self, request):
        refresh_token: str | None = request.data.get("refresh_token")
        if not refresh_token:
            return Response({"detail": "refresh_token is required."}, status=400)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response({"detail": "Invalid refresh_token."}, status=400)
        except Exception:
            return Response(
                {"detail": "Unable to blacklist refresh_token."}, status=400
            )
        return Response(status=204)


class MeView(APIView):
    permission_classes = [IsAuthenticated, IsApproved]

    @extend_schema(
        tags=["Authentication"],
        summary="Get current user",
        description="Returns profile details for the authenticated user.",
        responses={200: UserMeSerializer},
    )
    def get(self, request):
        serializer = UserMeSerializer(request.user)
        return Response(serializer.data, status=200)

