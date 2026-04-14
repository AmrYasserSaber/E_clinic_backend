from django.urls import path
from drf_spectacular.utils import extend_schema
from rest_framework_simplejwt.views import TokenRefreshView

from users.views import (
    ChangePasswordView,
    GoogleCallbackView,
    GoogleCompleteView,
    GooglePrefillView,
    GoogleStartView,
    LoginView,
   
    LogoutView,
   
    MeView,
    SetPasswordWithOtpView,
   
    SignupView,
)
from users.serializers import (
    ApprovalAwareTokenRefreshSerializer,
    MessageResponseSerializer,
    TokenRefreshRequestSerializer,
    TokenRefreshResponseSerializer,
)


class CustomTokenRefreshView(TokenRefreshView):
    serializer_class = ApprovalAwareTokenRefreshSerializer

    @extend_schema(
        tags=["Authentication"],
        summary="Refresh access token",
        description=(
            "Generates a new access token using a valid refresh token. "
            "Unapproved doctor/receptionist accounts receive 403."
        ),
        request=TokenRefreshRequestSerializer,
        responses={
            200: TokenRefreshResponseSerializer,
            401: MessageResponseSerializer,
            403: MessageResponseSerializer,
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    path("login/", LoginView.as_view(), name="login"),
    path("set-password-otp/", SetPasswordWithOtpView.as_view(), name="set_password_otp"),
    path("change-password/", ChangePasswordView.as_view(), name="change_password"),
    path("google/start/", GoogleStartView.as_view(), name="google_start"),
    path("google/callback/", GoogleCallbackView.as_view(), name="google_callback"),
    path("google/prefill/", GooglePrefillView.as_view(), name="google_prefill"),
    path("google/complete/", GoogleCompleteView.as_view(), name="google_complete"),
    path("refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
]
