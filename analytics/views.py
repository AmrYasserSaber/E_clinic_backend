from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Count, Q
from django.db.models.functions import ExtractHour, TruncDate, TruncWeek
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer

from appointments.models import Appointment, AppointmentStatus
from users.permissions import IsAdmin


def _parse_date(value: str | None, field_name: str) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({field_name: f"Invalid {field_name}. Expected YYYY-MM-DD."}) from exc


def _filtered_queryset(request):
    date_from = _parse_date(request.query_params.get("date_from"), "date_from")
    date_to = _parse_date(request.query_params.get("date_to"), "date_to")
    doctor_id = request.query_params.get("doctor_id")

    if date_from and date_to and date_from > date_to:
        raise ValidationError({"date_to": "date_to must be greater than or equal to date_from."})

    queryset = Appointment.objects.select_related("doctor")

    if date_from:
        queryset = queryset.filter(appointment_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(appointment_date__lte=date_to)
    if doctor_id not in (None, ""):
        try:
            doctor_id_int = int(doctor_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError({"doctor_id": "doctor_id must be an integer."}) from exc
        queryset = queryset.filter(doctor_id=doctor_id_int)

    return queryset


class AnalyticsSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        tags=["Analytics"],
        summary="Summary analytics",
        description="Returns appointment summary metrics for a date range and optional doctor.",
        parameters=[
            OpenApiParameter("date_from", str, OpenApiParameter.QUERY, description="Start date in YYYY-MM-DD format."),
            OpenApiParameter("date_to", str, OpenApiParameter.QUERY, description="End date in YYYY-MM-DD format."),
            OpenApiParameter("doctor_id", int, OpenApiParameter.QUERY, description="Filter by doctor ID."),
        ],
        responses={
            200: inline_serializer(
                name="AnalyticsSummaryResponse",
                fields={
                    "total_all_time": serializers.IntegerField(),
                    "total_this_week": serializers.IntegerField(),
                    "total_this_month": serializers.IntegerField(),
                    "status_breakdown": serializers.DictField(child=serializers.IntegerField()),
                    "no_show_rate": serializers.FloatField(),
                },
            )
        },
    )
    def get(self, request):
        queryset = _filtered_queryset(request)
        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        total_all_time = queryset.count()
        total_this_week = queryset.filter(appointment_date__gte=week_start, appointment_date__lte=today).count()
        total_this_month = queryset.filter(appointment_date__gte=month_start, appointment_date__lte=today).count()

        status_breakdown = {
            row["status"]: row["count"]
            for row in queryset.values("status").annotate(count=Count("id")).order_by("status")
        }
        no_show_count = status_breakdown.get(AppointmentStatus.NO_SHOW, 0)
        no_show_rate = 0.0
        if total_all_time:
            no_show_rate = round((no_show_count / total_all_time) * 100, 2)

        return Response(
            {
                "total_all_time": total_all_time,
                "total_this_week": total_this_week,
                "total_this_month": total_this_month,
                "status_breakdown": status_breakdown,
                "no_show_rate": no_show_rate,
            }
        )


class AnalyticsPeakHoursView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        tags=["Analytics"],
        summary="Peak hours analytics",
        description="Returns appointment counts grouped by hour.",
        parameters=[
            OpenApiParameter("date_from", str, OpenApiParameter.QUERY, description="Start date in YYYY-MM-DD format."),
            OpenApiParameter("date_to", str, OpenApiParameter.QUERY, description="End date in YYYY-MM-DD format."),
            OpenApiParameter("doctor_id", int, OpenApiParameter.QUERY, description="Filter by doctor ID."),
        ],
        responses={
            200: inline_serializer(
                name="AnalyticsPeakHoursResponse",
                fields={
                    "items": serializers.ListField(
                        child=serializers.DictField(),
                        help_text="List of hour buckets and counts.",
                    )
                },
            )
        },
    )
    def get(self, request):
        queryset = _filtered_queryset(request)
        items = (
            queryset
            .annotate(hour=ExtractHour("appointment_time"))
            .values("hour")
            .annotate(count=Count("id"))
            .order_by("hour")
        )
        return Response({"items": [{"hour": row["hour"], "count": row["count"]} for row in items]})


class AnalyticsByDoctorView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        tags=["Analytics"],
        summary="Analytics by doctor",
        description="Returns aggregated appointment metrics per doctor.",
        parameters=[
            OpenApiParameter("date_from", str, OpenApiParameter.QUERY, description="Start date in YYYY-MM-DD format."),
            OpenApiParameter("date_to", str, OpenApiParameter.QUERY, description="End date in YYYY-MM-DD format."),
            OpenApiParameter("doctor_id", int, OpenApiParameter.QUERY, description="Filter by doctor ID."),
        ],
        responses={
            200: inline_serializer(
                name="AnalyticsByDoctorResponse",
                fields={
                    "items": serializers.ListField(
                        child=serializers.DictField(),
                        help_text="List of doctor statistics.",
                    )
                },
            )
        },
    )
    def get(self, request):
        queryset = _filtered_queryset(request)
        rows = (
            queryset.values(
                "doctor_id",
                "doctor__first_name",
                "doctor__last_name",
                "doctor__email",
            )
            .annotate(
                total=Count("id"),
                completed=Count("id", filter=Q(status=AppointmentStatus.COMPLETED)),
                cancelled=Count("id", filter=Q(status=AppointmentStatus.CANCELLED)),
                no_show=Count("id", filter=Q(status=AppointmentStatus.NO_SHOW)),
                confirmed=Count("id", filter=Q(status=AppointmentStatus.CONFIRMED)),
                requested=Count("id", filter=Q(status=AppointmentStatus.REQUESTED)),
                checked_in=Count("id", filter=Q(status=AppointmentStatus.CHECKED_IN)),
            )
            .order_by("doctor__first_name", "doctor__last_name", "doctor_id")
        )

        items = []
        for row in rows:
            total = row["total"] or 0
            no_show_rate = round((row["no_show"] / total) * 100, 2) if total else 0.0
            items.append(
                {
                    "doctor_id": row["doctor_id"],
                    "doctor_name": f"{row['doctor__first_name']} {row['doctor__last_name']}".strip(),
                    "doctor_email": row["doctor__email"],
                    "total": total,
                    "completed": row["completed"],
                    "cancelled": row["cancelled"],
                    "no_show": row["no_show"],
                    "requested": row["requested"],
                    "confirmed": row["confirmed"],
                    "checked_in": row["checked_in"],
                    "no_show_rate": no_show_rate,
                }
            )
        return Response({"items": items})


class AnalyticsNoShowRateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        tags=["Analytics"],
        summary="No-show rate trend",
        description="Returns no-show rate over time.",
        parameters=[
            OpenApiParameter("date_from", str, OpenApiParameter.QUERY, description="Start date in YYYY-MM-DD format."),
            OpenApiParameter("date_to", str, OpenApiParameter.QUERY, description="End date in YYYY-MM-DD format."),
            OpenApiParameter("group_by", str, OpenApiParameter.QUERY, description="Grouping interval: day or week."),
        ],
        responses={
            200: inline_serializer(
                name="AnalyticsNoShowRateResponse",
                fields={
                    "items": serializers.ListField(
                        child=serializers.DictField(),
                        help_text="List of date buckets and no-show percentages.",
                    ),
                    "group_by": serializers.CharField(),
                },
            )
        },
    )
    def get(self, request):
        queryset = _filtered_queryset(request)
        group_by = (request.query_params.get("group_by") or "day").lower()

        bucket_expression = TruncDate("appointment_date") if group_by == "day" else TruncWeek("appointment_date")
        rows = (
            queryset.annotate(period=bucket_expression)
            .values("period")
            .annotate(
                total=Count("id"),
                no_show=Count("id", filter=Q(status=AppointmentStatus.NO_SHOW)),
            )
            .order_by("period")
        )
        items = []
        for row in rows:
            total = row["total"] or 0
            no_show_rate = round((row["no_show"] / total) * 100, 2) if total else 0.0
            items.append(
                {
                    "period": row["period"],
                    "total": total,
                    "no_show": row["no_show"],
                    "no_show_rate": no_show_rate,
                }
            )
        return Response({"items": items, "group_by": group_by})