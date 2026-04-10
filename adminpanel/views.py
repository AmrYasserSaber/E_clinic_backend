from __future__ import annotations

from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.models import User
from users.permissions import IsAdmin, IsAdminOrDoctorOrReceptionist

from .serializers import (
    AdminUserCreateSerializer,
    AdminUserListSerializer,
    AdminUserUpdateSerializer,
    PatientListSerializer,
)


class AdminUserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdmin]
    queryset = User.objects.all().prefetch_related("groups")

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
        return Response({"detail": "User deactivated successfully."}, status=status.HTTP_200_OK)


class PatientViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminOrDoctorOrReceptionist]
    serializer_class = PatientListSerializer

    def get_queryset(self):
        return (
            User.objects.filter(groups__name="Patient")
            .prefetch_related("groups")
            .order_by("-id")
        )