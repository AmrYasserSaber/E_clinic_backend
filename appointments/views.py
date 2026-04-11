from __future__ import annotations

import datetime as dt

from django.contrib.auth import get_user_model
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from appointments.serializers import AvailableSlotSerializer
from appointments.slot_generation import iter_available_slots

User = get_user_model()


class AvailableSlotsView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="doctor_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=True,
            ),
            OpenApiParameter(
                name="date",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Calendar date (YYYY-MM-DD).",
            ),
        ],
        responses={200: AvailableSlotSerializer(many=True)},
    )
    def get(self, request):
        doctor_id_raw = request.query_params.get("doctor_id")
        date_raw = request.query_params.get("date")
        if (
            doctor_id_raw is None
            or date_raw is None
            or str(doctor_id_raw).strip() == ""
            or str(date_raw).strip() == ""
        ):
            return Response({"detail": "doctor_id and date are required."}, status=400)
        try:
            doctor_id = int(doctor_id_raw)
        except (TypeError, ValueError):
            return Response({"detail": "doctor_id must be an integer."}, status=400)
        try:
            target_date = dt.date.fromisoformat(date_raw)
        except ValueError:
            return Response({"detail": "date must be YYYY-MM-DD."}, status=400)

        if target_date < timezone.localdate():
            return Response({"detail": "Cannot list slots for past dates."}, status=400)

        if not User.objects.filter(pk=doctor_id, groups__name="Doctor").exists():
            return Response({"detail": "Doctor not found."}, status=404)

        slots = iter_available_slots(doctor_id, target_date)
        rows = []
        for s in slots:
            ls = timezone.localtime(s["start"])
            le = timezone.localtime(s["end"])
            rows.append(
                {
                    "doctorId": s["doctor_id"],
                    "date": s["date"],
                    "startTime": ls.time().replace(microsecond=0),
                    "endTime": le.time().replace(microsecond=0),
                }
            )
        serializer = AvailableSlotSerializer(rows, many=True)
        return Response(serializer.data, status=200)
