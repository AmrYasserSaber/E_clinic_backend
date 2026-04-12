from __future__ import annotations

import csv
from datetime import date

from django.db.models import Count
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from appointments.models import Appointment, AppointmentStatus
from users.permissions import IsAdmin
from users.serializers import MessageResponseSerializer


def _parse_date(value: str | None, field_name: str) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({field_name: f"Invalid {field_name}. Expected YYYY-MM-DD."}) from exc


class AppointmentExportCsvView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        tags=["Reports"],
        summary="Export appointments as CSV",
        description="Exports appointments using optional filters. Admin-only endpoint.",
        parameters=[
            OpenApiParameter("format", str, OpenApiParameter.QUERY, description="Only `csv` is supported."),
            OpenApiParameter("date_from", str, OpenApiParameter.QUERY, description="Start date in YYYY-MM-DD format."),
            OpenApiParameter("date_to", str, OpenApiParameter.QUERY, description="End date in YYYY-MM-DD format."),
            OpenApiParameter("doctor_id", int, OpenApiParameter.QUERY, description="Filter by doctor ID."),
            OpenApiParameter("status", str, OpenApiParameter.QUERY, description="Filter by appointment status."),
        ],
        responses={200: None, 400: MessageResponseSerializer, 403: MessageResponseSerializer},
    )
    def get(self, request):
        output_format = (request.query_params.get("format") or "csv").lower()
        if output_format != "csv":
            raise ValidationError({"format": "Only csv format is supported."})

        date_from = _parse_date(request.query_params.get("date_from"), "date_from")
        date_to = _parse_date(request.query_params.get("date_to"), "date_to")
        doctor_id = request.query_params.get("doctor_id")
        status_values = request.query_params.getlist("status")

        if date_from and date_to and date_from > date_to:
            raise ValidationError({"date_to": "date_to must be greater than or equal to date_from."})

        queryset = (
            Appointment.objects.select_related("patient", "doctor")
            .annotate(reschedule_count=Count("reschedule_history", distinct=True))
            .order_by("appointment_date", "appointment_time", "id")
        )
        if date_from:
            queryset = queryset.filter(appointment_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(appointment_date__lte=date_to)
        if doctor_id not in (None, ""):
            try:
                queryset = queryset.filter(doctor_id=int(doctor_id))
            except (TypeError, ValueError) as exc:
                raise ValidationError({"doctor_id": "doctor_id must be an integer."}) from exc

        if status_values:
            normalized = [value.upper() for value in status_values if value]
            valid_statuses = {choice for choice, _ in AppointmentStatus.choices}
            invalid = [value for value in normalized if value not in valid_statuses]
            if invalid:
                raise ValidationError({"status": f"Invalid status values: {', '.join(invalid)}."})
            queryset = queryset.filter(status__in=normalized)

        filename_from = date_from.isoformat() if date_from else "all"
        filename_to = date_to.isoformat() if date_to else "all"
        filename = f"appointments_{filename_from}_to_{filename_to}.csv"

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "Appointment ID",
                "Patient Name",
                "Patient Email",
                "Doctor Name",
                "Specialty",
                "Date",
                "Time",
                "Status",
                "Reason",
                "Check-In Time",
                "Duration",
                "Reschedule Count",
            ]
        )

        for appointment in queryset:
            patient_name = f"{appointment.patient.first_name} {appointment.patient.last_name}".strip()
            doctor_name = f"{appointment.doctor.first_name} {appointment.doctor.last_name}".strip()
            writer.writerow(
                [
                    appointment.id,
                    patient_name,
                    appointment.patient.email,
                    doctor_name,
                    appointment.doctor.specialty,
                    appointment.appointment_date.isoformat(),
                    appointment.appointment_time.strftime("%H:%M:%S"),
                    appointment.status,
                    appointment.reason,
                    appointment.check_in_time.isoformat() if appointment.check_in_time else "",
                    appointment.session_duration_minutes,
                    appointment.reschedule_count,
                ]
            )

        return response