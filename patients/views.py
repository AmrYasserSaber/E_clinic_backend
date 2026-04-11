from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsApproved, IsPatient
from users.serializers import UserMeSerializer


class PatientMeView(APIView):
    permission_classes = [IsAuthenticated, IsApproved, IsPatient]

    def get(self, request):
        serializer = UserMeSerializer(request.user)
        return Response(serializer.data, status=200)
