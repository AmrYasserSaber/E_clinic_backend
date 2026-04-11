from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from appointments.serializers import AppointmentBookingSerializer, AppointmentSerializer
from appointments.services import BookingConflictError
from users.permissions import IsApproved, IsPatient


class AppointmentBookingView(APIView):
    permission_classes = [IsAuthenticated, IsApproved, IsPatient]

    def post(self, request):
        booking_serializer = AppointmentBookingSerializer(data=request.data)
        booking_serializer.is_valid(raise_exception=True)

        try:
            appointment = booking_serializer.save(patient=request.user)
        except BookingConflictError as exc:
            return Response({"detail": str(exc)}, status=409)

        response_serializer = AppointmentSerializer(appointment)
        return Response(response_serializer.data, status=201)
