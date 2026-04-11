from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import serializers
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer

from users.permissions import IsAdmin


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
        # TODO: parse date_from/date_to/doctor_id
        # TODO: aggregate totals + status breakdown + no-show rate
        return Response(
            {
                "total_all_time": 0,
                "total_this_week": 0,
                "total_this_month": 0,
                "status_breakdown": {},
                "no_show_rate": 0.0,
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
        # TODO: group appointments by hour
        return Response({"items": []})


class AnalyticsByDoctorView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        tags=["Analytics"],
        summary="Analytics by doctor",
        description="Returns aggregated appointment metrics per doctor.",
        parameters=[
            OpenApiParameter("date_from", str, OpenApiParameter.QUERY, description="Start date in YYYY-MM-DD format."),
            OpenApiParameter("date_to", str, OpenApiParameter.QUERY, description="End date in YYYY-MM-DD format."),
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
        # TODO: per-doctor stats
        return Response({"items": []})


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
                    )
                },
            )
        },
    )
    def get(self, request):
        # TODO: no-show trend by day/week
        return Response({"items": []})