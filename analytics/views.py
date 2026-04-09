from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response

from users.permissions import IsAdmin


class AnalyticsSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

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

    def get(self, request):
        # TODO: group appointments by hour
        return Response({"items": []})


class AnalyticsByDoctorView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        # TODO: per-doctor stats
        return Response({"items": []})


class AnalyticsNoShowRateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        # TODO: no-show trend by day/week
        return Response({"items": []})