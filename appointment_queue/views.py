from __future__ import annotations

from datetime import date, datetime

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from appointments.models import Appointment, AppointmentStatus
from users.models import User
from users.permissions import IsAdminOrDoctorOrReceptionist, IsApproved

from .serializers import DoctorAvailabilitySerializer, QueueItemSerializer, QueueQuerySerializer


class QueueListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrDoctorOrReceptionist]

    @extend_schema(
        tags=["doctors", "Queue"],
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

        date_raw = query_serializer.validated_data.get("date")
        if not date_raw or str(date_raw).lower() == "today":
            target_date = timezone.localdate()
        else:
            try:
                target_date = date.fromisoformat(date_raw)
            except ValueError:
                return Response({"detail": "date must be YYYY-MM-DD or 'today'."}, status=400)

        doctor_id = query_serializer.validated_data.get("doctor_id")

        queryset = Appointment.objects.filter(
            appointment_date=target_date,
            status__in=[AppointmentStatus.CONFIRMED, AppointmentStatus.CHECKED_IN],
        )

        if doctor_id:
            queryset = queryset.filter(doctor_id=doctor_id)

        queryset = queryset.select_related("patient", "doctor")

        queue_rows = list(
            queryset.order_by(
                "status",
                "check_in_time",
                "appointment_time",
            )
        )

        # Queue order:
        # 1) checked_in (check_in_time ASC)
        # 2) confirmed (time ASC)
        checked_in_rows = [r for r in queue_rows if r.status == AppointmentStatus.CHECKED_IN]
        confirmed_rows = [r for r in queue_rows if r.status == AppointmentStatus.CONFIRMED]

        checked_in_rows.sort(key=lambda r: (r.check_in_time or timezone.now(), r.appointment_time))
        confirmed_rows.sort(key=lambda r: r.appointment_time)

        ordered_rows = checked_in_rows + confirmed_rows

        now = timezone.now()
        result = []
        for index, row in enumerate(ordered_rows):
            patient_obj = getattr(row, "patient", None)
            first_name = getattr(patient_obj, "first_name", "") or ""
            last_name = getattr(patient_obj, "last_name", "") or ""
            patient_name = f"{first_name} {last_name}".strip()

            doctor_obj = getattr(row, "doctor", None)
            doctor_first = getattr(doctor_obj, "first_name", "") or ""
            doctor_last = getattr(doctor_obj, "last_name", "") or ""
            doctor_name = f"{doctor_first} {doctor_last}".strip() or getattr(doctor_obj, "email", "") or "Assigned Doctor"

            if row.status == AppointmentStatus.CHECKED_IN and row.check_in_time:
                waiting_delta = now - row.check_in_time
            else:
                appointment_dt = timezone.make_aware(
                    datetime.combine(row.appointment_date, row.appointment_time),
                    timezone.get_current_timezone(),
                )
                waiting_delta = now - appointment_dt

            waiting_time = max(0, int(waiting_delta.total_seconds() // 60))

            result.append(
                {
                    "queue_position": index + 1,
                    "waiting_time": waiting_time,
                    "patient_name": patient_name,
                    "doctor_name": doctor_name,
                    "appointment_id": row.id,
                    "doctor_id": row.doctor_id,
                    "date": row.appointment_date,
                    "time": row.appointment_time,
                    "status": row.status,
                    "check_in_time": row.check_in_time,
                }
            )

        serializer = QueueItemSerializer(result, many=True)
        return Response(serializer.data, status=200)


class DoctorsAvailabilityView(APIView):
    permission_classes = [IsAuthenticated, IsApproved]

    @extend_schema(
        tags=["doctors", "Queue"],
        summary="Get doctors availability",
        description="Returns doctor availability status for today.",
        responses={200: DoctorAvailabilitySerializer(many=True)},
    )
    def get(self, request):
        today = timezone.localdate()
        doctors = User.objects.filter(groups__name="Doctor", is_active=True).distinct().order_by("id")

        busy_doctor_ids = set(
            Appointment.objects.filter(
                appointment_date=today,
                status=AppointmentStatus.CHECKED_IN,
            ).values_list("doctor_id", flat=True)
        )

        confirmed_doctor_ids = set(
            Appointment.objects.filter(
                appointment_date=today,
                status=AppointmentStatus.CONFIRMED,
            ).values_list("doctor_id", flat=True)
        )

        rows = []
        for doctor in doctors:
            if doctor.id in busy_doctor_ids:
                status = "BUSY"
            elif doctor.id in confirmed_doctor_ids:
                status = "AVAILABLE"
            else:
                status = "AWAY"

            full_name = f"{doctor.first_name} {doctor.last_name}".strip() or doctor.email
            rows.append(
                {
                    "id": doctor.id,
                    "name": full_name,
                    "specialty": doctor.specialty or "General Practitioner",
                    "status": status,
                }
            )

        return Response(DoctorAvailabilitySerializer(rows, many=True).data, status=200)
