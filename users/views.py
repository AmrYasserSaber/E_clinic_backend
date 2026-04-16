from __future__ import annotations

from django.contrib.auth import get_user_model
import secrets

from django.conf import settings
from django.shortcuts import redirect
from django.utils import timezone as django_timezone
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema

from users.google_oauth_service import GoogleOAuthService, GoogleOneTimeCodePayload
from users.permissions import IsApproved
from users.password_otp import verify_otp
from users.serializers import (
    ChangePasswordSerializer,
    GoogleCompleteIntent,
    GoogleCompleteRequestSerializer,
    GooglePrefillRequestSerializer,
    GooglePrefillResponseSerializer,
    GoogleStartResponseSerializer,
    LoginResponseSerializer,
    LoginSerializer,
    LogoutRequestSerializer,
    MessageResponseSerializer,
    SetPasswordWithOtpSerializer,
    SignupResponseSerializer,
    SignupSerializer,
    UserMeSerializer,
)
from django.contrib.auth.models import Group
from users.welcome_email import send_welcome_email

User = get_user_model()


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


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated, IsApproved]

    @extend_schema(
        tags=["Authentication"],
        summary="Change current password",
        description="Changes password for the authenticated user.",
        request=ChangePasswordSerializer,
        responses={200: MessageResponseSerializer, 400: MessageResponseSerializer},
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return Response({"detail": "Password changed successfully."}, status=200)


class SetPasswordWithOtpView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Authentication"],
        summary="Set password using OTP",
        description=(
            "Sets password using the one-time password emailed when the account is created "
            "by an administrator."
        ),
        request=SetPasswordWithOtpSerializer,
        responses={200: MessageResponseSerializer, 400: MessageResponseSerializer},
    )
    def post(self, request):
        serializer = SetPasswordWithOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]
        if not verify_otp(email, otp):
            return Response({"detail": "Invalid or expired OTP."}, status=400)

        user = User.objects.get(email=email)
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response({"detail": "Password set successfully."}, status=200)


class GoogleStartView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Authentication"],
        summary="Start Google OAuth2",
        description="Returns a Google authorization URL for login or signup intents.",
        responses={200: GoogleStartResponseSerializer, 400: MessageResponseSerializer},
    )
    def get(self, request):
        intent: str | None = request.query_params.get("intent")
        if intent not in {GoogleCompleteIntent.LOGIN, GoogleCompleteIntent.SIGNUP}:
            return Response({"detail": "intent must be login or signup."}, status=400)
        service = GoogleOAuthService()
        authorization_url: str = service.build_authorization_url(intent=intent)
        return Response({"authorization_url": authorization_url}, status=200)


class GoogleCallbackView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Authentication"],
        summary="Google OAuth2 callback",
        description=(
            "Exchanges code with Google, verifies id_token, then redirects to the frontend "
            "with a short-lived one-time code for completion."
        ),
        responses={302: None, 400: MessageResponseSerializer},
    )
    def get(self, request):
        code: str | None = request.query_params.get("code")
        state: str | None = request.query_params.get("state")
        if not code or not state:
            return Response({"detail": "code and state are required."}, status=400)
        service = GoogleOAuthService()
        try:
            state_payload = service.validate_state(state=state)
        except ValueError as err:
            return Response({"detail": str(err)}, status=400)
        intent = state_payload.get("intent")
        nonce = state_payload.get("nonce")
        if intent not in {GoogleCompleteIntent.LOGIN, GoogleCompleteIntent.SIGNUP}:
            return Response({"detail": "Invalid intent in state."}, status=400)
        if not isinstance(nonce, str) or not nonce:
            return Response({"detail": "Invalid nonce in state."}, status=400)
        try:
            exchange = service.exchange_code_for_tokens(code=code)
            claims = service.verify_id_token(id_token_value=exchange.id_token, expected_nonce=nonce)
        except Exception:
            return Response({"detail": "Unable to validate Google sign-in."}, status=400)
        one_time_payload = GoogleOneTimeCodePayload(
            jti=secrets.token_urlsafe(24),
            sub=claims.sub,
            email=claims.email,
            email_verified=claims.email_verified,
            given_name=claims.given_name,
            family_name=claims.family_name,
            intent=intent,
        )
        one_time_code: str = service.create_one_time_code(payload=one_time_payload)
        if request.query_params.get("format") == "json":
            return Response({"one_time_code": one_time_code, "intent": intent}, status=200)
        frontend_url: str = getattr(settings, "GOOGLE_OAUTH_FRONTEND_COMPLETE_URL", "")
        if not frontend_url:
            return Response({"detail": "Frontend redirect URL not configured."}, status=400)
        split = urlsplit(frontend_url)
        query = dict(parse_qsl(split.query, keep_blank_values=True))
        query.update({"one_time_code": one_time_code, "intent": intent})
        redirect_url = urlunsplit((split.scheme, split.netloc, split.path, urlencode(query), split.fragment))
        return redirect(redirect_url)


class GooglePrefillView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Authentication"],
        summary="Prefill Google signup fields",
        description="Decodes the one-time code (without consuming it) to prefill name/email.",
        request=GooglePrefillRequestSerializer,
        responses={200: GooglePrefillResponseSerializer, 400: MessageResponseSerializer},
    )
    def post(self, request):
        serializer = GooglePrefillRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = GoogleOAuthService()
        try:
            payload = service.peek_one_time_code(one_time_code=serializer.validated_data["one_time_code"])
        except ValueError as err:
            return Response({"detail": str(err)}, status=400)
        return Response(
            {
                "email": payload.email,
                "first_name": payload.given_name,
                "last_name": payload.family_name,
            },
            status=200,
        )


class GoogleCompleteView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Authentication"],
        summary="Complete Google OAuth2",
        description="Consumes one-time code, links Google account, and returns JWTs.",
        request=GoogleCompleteRequestSerializer,
        responses={
            200: LoginResponseSerializer,
            201: LoginResponseSerializer,
            400: MessageResponseSerializer,
            403: MessageResponseSerializer,
        },
    )
    def post(self, request):
        serializer = GoogleCompleteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = GoogleOAuthService()
        try:
            payload = service.consume_one_time_code(one_time_code=serializer.validated_data["one_time_code"])
        except ValueError as err:
            return Response({"detail": str(err)}, status=400)
        intent: str = serializer.validated_data["intent"]
        if payload.intent != intent:
            return Response({"detail": "Intent mismatch."}, status=400)
        if intent == GoogleCompleteIntent.LOGIN:
            return self._execute_login(request=request, payload=payload)
        return self._execute_signup(request=request, payload=payload, signup_data=serializer.validated_data)

    def _execute_login(self, *, request, payload: GoogleOneTimeCodePayload) -> Response:
        try:
            user: User = User.objects.get(email=payload.email)
        except User.DoesNotExist:
            return Response({"detail": "No account found for this email."}, status=400)
        link_error = self._link_google_identity(user=user, payload=payload)
        if link_error:
            return Response({"detail": link_error}, status=400)
        if not IsApproved.may_receive_tokens(user):
            return Response({"detail": IsApproved.message}, status=403)
        refresh = RefreshToken.for_user(user)
        user_serializer = UserMeSerializer(user)
        return Response(
            {
                "user": user_serializer.data,
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
            },
            status=200,
        )

    def _execute_signup(self, *, request, payload: GoogleOneTimeCodePayload, signup_data: dict) -> Response:
        role: str = signup_data["role"]
        if role != "patient":
            return Response({"detail": "Only patient signup is allowed with Google."}, status=400)
        user = User.objects.filter(email=payload.email).first()
        created = False
        if user and not user.groups.filter(name="Patient").exists():
            return Response({"detail": "This email is already registered to a non-patient account."}, status=400)
        if not user:
            first_name: str = str(signup_data.get("first_name") or payload.given_name or "").strip()
            last_name: str = str(signup_data.get("last_name") or payload.family_name or "").strip()
            if not first_name:
                first_name = payload.email.split("@", 1)[0][:150] or "Patient"
            if not last_name:
                last_name = "User"
            user = User.objects.create_user(
                email=payload.email,
                password=None,
                first_name=first_name,
                last_name=last_name,
                phone_number=signup_data.get("phone_number") or None,
                date_of_birth=signup_data.get("date_of_birth") or None,
                is_approved=True,
            )
            group: Group = Group.objects.get(name="Patient")
            user.groups.add(group)
            created = True
            try:
                send_welcome_email(user=user, role="patient")
            except Exception:
                pass
        link_error = self._link_google_identity(user=user, payload=payload)
        if link_error:
            return Response({"detail": link_error}, status=400)
        if not IsApproved.may_receive_tokens(user):
            return Response({"detail": IsApproved.message}, status=403)
        refresh = RefreshToken.for_user(user)
        user_serializer = UserMeSerializer(user)
        return Response(
            {
                "user": user_serializer.data,
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
            },
            status=201 if created else 200,
        )

    def _link_google_identity(self, *, user: User, payload: GoogleOneTimeCodePayload) -> str | None:
        if not payload.email_verified:
            return "Google account email is not verified."
        if user.google_sub and user.google_sub != payload.sub:
            return "This account is already linked to a different Google profile."
        other = User.objects.filter(google_sub=payload.sub).exclude(pk=user.pk).first()
        if other:
            return "This Google profile is already linked to another account."
        user.google_sub = payload.sub
        user.google_email = payload.email
        user.google_linked_at = django_timezone.now()
        user.save(update_fields=["google_sub", "google_email", "google_linked_at"])
        return None

