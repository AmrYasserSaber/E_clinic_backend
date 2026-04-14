from __future__ import annotations

from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view

from users.models import User
from users.permissions import IsAdmin, IsAdminOrDoctorOrReceptionist
from users.serializers import MessageResponseSerializer

from users.welcome_email import send_profile_updated_email

from .serializers import (
    AdminUserCreateSerializer,
    AdminUserListSerializer,
    AdminUserUpdateSerializer,
    PatientListSerializer,
)


@extend_schema_view(
    create=extend_schema(
        tags=["Admin Users"],
        summary="Create user",
        request=AdminUserCreateSerializer,
        responses={201: AdminUserListSerializer, 400: MessageResponseSerializer},
    ),
    retrieve=extend_schema(
        tags=["Admin Users"],
        summary="Get user by ID",
        responses={200: AdminUserListSerializer, 404: MessageResponseSerializer},
    ),
    update=extend_schema(
        tags=["Admin Users"],
        summary="Replace user",
        request=AdminUserUpdateSerializer,
        responses={200: AdminUserListSerializer, 400: MessageResponseSerializer},
    ),
    partial_update=extend_schema(
        tags=["Admin Users"],
        summary="Partially update user",
        request=AdminUserUpdateSerializer,
        responses={200: AdminUserListSerializer, 400: MessageResponseSerializer},
    ),
)
class AdminUserViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "patch", "put", "head", "options"]
    permission_classes = [IsAuthenticated, IsAdmin]
    queryset = User.objects.all().prefetch_related("groups")
    
    class AdminUserPagination(PageNumberPagination):
        page_size = 20
        page_size_query_param = "page_size"
        max_page_size = 100

    pagination_class = AdminUserPagination

    def get_serializer_class(self):
        if self.action == "create":
            return AdminUserCreateSerializer
        if self.action in ["partial_update", "update"]:
            return AdminUserUpdateSerializer
        return AdminUserListSerializer

    def get_queryset(self):
        qs = super().get_queryset()

        search = self.request.query_params.get("search")
        role = self.request.query_params.get("role")
        is_active = self.request.query_params.get("is_active")

        if search:
            qs = qs.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
            )

        if role:
            qs = qs.filter(groups__name__iexact=role)

        if is_active is not None:
            qs = qs.filter(is_active=(is_active.lower() == "true"))

        return qs.distinct().order_by("-id")

    @extend_schema(
        tags=["Admin Users"],
        summary="List users",
        description="Returns users with optional filters by `search`, `role`, and `is_active`.",
        parameters=[
            OpenApiParameter(
                name="search",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by first name, last name, or email.",
            ),
            OpenApiParameter(
                name="role",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Role filter: admin, doctor, receptionist, or patient.",
            ),
            OpenApiParameter(
                name="is_active",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filter by active status.",
            ),
            OpenApiParameter(
                name="page",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Page number.",
            ),
            OpenApiParameter(
                name="page_size",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Items per page (max 100).",
            ),
        ],
        responses={200: AdminUserListSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=["Admin Users"],
        summary="Deactivate user",
        description="Sets `is_active` to `false` for a user account.",
        request=None,
        responses={200: MessageResponseSerializer, 400: MessageResponseSerializer},
    )
    @action(detail=True, methods=["patch"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        target = self.get_object()

        if target.id == request.user.id:
            return Response(
                {"detail": "You cannot deactivate your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target.is_active = False
        target.save(update_fields=["is_active"])

        send_profile_updated_email(
            user=target,
            changes=[{
                "field": "Account Active",
                "old_value": "Yes",
                "new_value": "No",
            }],
        )

        return Response({"detail": "User deactivated successfully."}, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(
        tags=["Patients"],
        summary="List patients",
        responses={200: PatientListSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["Patients"],
        summary="Get patient by ID",
        responses={200: PatientListSerializer, 404: MessageResponseSerializer},
    ),
)
class PatientViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminOrDoctorOrReceptionist]
    serializer_class = PatientListSerializer

    def get_queryset(self):
        return (
            User.objects.filter(groups__name="Patient")
            .prefetch_related("groups")
            .order_by("-id")
        )