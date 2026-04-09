from __future__ import annotations

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from users.permissions import IsApproved
from users.serializers import LoginSerializer, SignupSerializer, UserMeSerializer


class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        user_serializer = UserMeSerializer(user)
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

    def post(self, request):
        refresh_token: str | None = request.data.get("refresh_token")
        if not refresh_token:
            return Response({"detail": "refresh_token is required."}, status=400)
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response(status=204)


class MeView(APIView):
    permission_classes = [IsAuthenticated, IsApproved]

    def get(self, request):
        serializer = UserMeSerializer(request.user)
        return Response(serializer.data, status=200)

