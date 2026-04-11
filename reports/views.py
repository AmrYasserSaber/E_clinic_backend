from __future__ import annotations

import csv
from datetime import datetime

from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from users.permissions import IsAdmin


class AppointmentExportCsvView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        tags=["Reports"],
        summary="Export appointments CSV",
        description="Exports appointments in CSV format filtered by optional date range.",
        parameters=[
            OpenApiParameter(
                name="date_from",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Start date in YYYY-MM-DD format. Defaults to 'all'.",
            ),
            OpenApiParameter(
                name="date_to",
                type=str,
                location=OpenApiParameter.QUERY,
                description="End date in YYYY-MM-DD format. Defaults to 'all'.",
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.BINARY,
                description="CSV file stream.",
            )
        },
    )
    def get(self, request):
        date_from = request.query_params.get("date_from", "all")
        date_to = request.query_params.get("date_to", "all")

        filename = f"appointments_{date_from}_to_{date_to}.csv"

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

        # TODO: query filtered appointments and write rows

        return response