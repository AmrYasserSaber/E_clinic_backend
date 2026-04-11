from __future__ import annotations

from datetime import datetime

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from appointments.models import Appointment
from users.permissions import IsAdminOrDoctorOrReceptionist

from .serializers import QueueItemSerializer, QueueQuerySerializer


class QueueListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrDoctorOrReceptionist]

    @extend_schema(
        tags=["Queue"],
        summary="Get queue",
        description="Returns queue entries filtered by optional date and doctor_id.",
        parameters=[
            OpenApiParameter(
                name="date",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Date in YYYY-MM-DD format. Defaults to today.",
                required=False,
            ),
            OpenApiParameter(
                name="doctor_id",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Filter queue by doctor ID.",
                required=False,
            ),
        ],
        responses={200: QueueItemSerializer(many=True)},
    )
    def get(self, request):
        query_serializer = QueueQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)

        target_date = query_serializer.validated_data.get("date", timezone.localdate())
        doctor_id = query_serializer.validated_data.get("doctor_id")

        queryset = Appointment.objects.filter(date=target_date, status__in=["confirmed", "checked_in"])

        if doctor_id:
            queryset = queryset.filter(doctor_id=doctor_id)

        queryset = queryset.select_related("patient", "doctor")

        queue_rows = list(
            queryset.order_by(
                "status",
                "check_in_time",
                "time",
            )
        )

        # Keep exact required order:
        # 1) checked_in (check_in_time ASC)
        # 2) confirmed (time ASC)
        checked_in_rows = [r for r in queue_rows if r.status == "checked_in"]
        confirmed_rows = [r for r in queue_rows if r.status == "confirmed"]

        checked_in_rows.sort(key=lambda r: (r.check_in_time or timezone.now(), r.time))
        confirmed_rows.sort(key=lambda r: r.time)

        ordered_rows = checked_in_rows + confirmed_rows

        now = timezone.now()
        result = []
        for index, row in enumerate(ordered_rows):
            patient_obj = getattr(row, "patient", None)
            nested_user = getattr(patient_obj, "user", None)
            first_name = (nested_user.first_name if nested_user else getattr(patient_obj, "first_name", "")) or ""
            last_name = (nested_user.last_name if nested_user else getattr(patient_obj, "last_name", "")) or ""
            patient_name = f"{first_name} {last_name}".strip()

            if row.status == "checked_in" and row.check_in_time:
                waiting_delta = now - row.check_in_time
            else:
                appointment_dt = timezone.make_aware(
                    datetime.combine(row.date, row.time),
                    timezone.get_current_timezone(),
                )
                waiting_delta = now - appointment_dt

            waiting_time = max(0, int(waiting_delta.total_seconds() // 60))

            result.append(
                {
                    "queue_position": index + 1,
                    "waiting_time": waiting_time,
                    "patient_name": patient_name,
                    "appointment_id": row.id,
                    "doctor_id": row.doctor_id,
                    "date": row.date,
                    "time": row.time,
                    "status": row.status,
                    "check_in_time": row.check_in_time,
                }
            )

        serializer = QueueItemSerializer(result, many=True)
        return Response(serializer.data, status=200)
