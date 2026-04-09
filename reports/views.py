from __future__ import annotations

import csv
from datetime import datetime

from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from users.permissions import IsAdmin


class AppointmentExportCsvView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    @extend_schema(
        responses={
            200: {
                "type": "object",
                "properties": {
                    "total_all_time": {"type": "integer"},
                    "total_this_week": {"type": "integer"},
                    "total_this_month": {"type": "integer"},
                    "status_breakdown": {"type": "object"},
                    "no_show_rate": {"type": "number"},
                },
            }
        }
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