from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from patients.models import PatientProfile
from patients.serializers import (
    PatientMeReadSerializer,
    PatientProfilePatchSerializer,
    PatientUserPatchSerializer,
)
from users.permissions import IsApproved, IsPatient


class PatientMeView(APIView):
    permission_classes = [IsAuthenticated, IsApproved, IsPatient]

    def get(self, request):
        serializer = PatientMeReadSerializer(request.user)
        return Response(serializer.data, status=200)

    def patch(self, request):
        user = request.user
        payload = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        profile_payload = payload.pop("profile", None)

        user_serializer = PatientUserPatchSerializer(user, data=payload, partial=True)
        user_serializer.is_valid(raise_exception=True)
        user_serializer.save()

        if profile_payload is not None:
            profile, _ = PatientProfile.objects.get_or_create(user=user)
            profile_serializer = PatientProfilePatchSerializer(
                profile, data=profile_payload, partial=True
            )
            profile_serializer.is_valid(raise_exception=True)
            profile_serializer.save()

        user.refresh_from_db()
        return Response(PatientMeReadSerializer(user).data, status=200)
