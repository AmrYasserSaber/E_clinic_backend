from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import User
from users.serializers import MessageResponseSerializer

from .models import DoctorSchedule, ScheduleException
from .serializers import (
    DoctorScheduleDayUpdateSerializer,
    DoctorScheduleSerializer,
    DoctorScheduleUpsertItemSerializer,
    ScheduleExceptionCreateSerializer,
    ScheduleExceptionSerializer,
)


class IsAdminOrReceptionist(BasePermission):
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.groups.filter(name__in=["Admin", "Receptionist"]).exists()
        )


class DoctorScheduleListUpsertView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrReceptionist]

    def _get_doctor(self, doctor_id: int) -> User:
        return get_object_or_404(User, id=doctor_id, groups__name="Doctor")

    @extend_schema(
        tags=["Schedules"],
        summary="List doctor schedule",
        description="Returns all schedule entries for a specific doctor.",
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="Doctor user ID.",
            )
        ],
        responses={200: DoctorScheduleSerializer(many=True)},
    )
    def get(self, request, id: int):
        doctor = self._get_doctor(id)
        queryset = DoctorSchedule.objects.filter(doctor=doctor).order_by("day_of_week", "start_time")
        serializer = DoctorScheduleSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Schedules"],
        summary="Upsert doctor weekly schedule",
        description="Accepts a list of schedule days and upserts one entry per `day_of_week`.",
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="Doctor user ID.",
            )
        ],
        request=DoctorScheduleUpsertItemSerializer(many=True),
        responses={200: DoctorScheduleSerializer(many=True)},
    )
    def post(self, request, id: int):
        doctor = self._get_doctor(id)
        serializer = DoctorScheduleUpsertItemSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        for item in serializer.validated_data:
            day = item["day_of_week"]
            DoctorSchedule.objects.update_or_create(
                doctor=doctor,
                day_of_week=day,
                defaults={
                    "start_time": item["start_time"],
                    "end_time": item["end_time"],
                    "session_duration_minutes": item["session_duration_minutes"],
                    "buffer_minutes": item.get("buffer_minutes", 5),
                },
            )

        updated = DoctorSchedule.objects.filter(doctor=doctor).order_by("day_of_week", "start_time")
        return Response(DoctorScheduleSerializer(updated, many=True).data, status=status.HTTP_200_OK)


class DoctorScheduleDayUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrReceptionist]

    def _get_doctor(self, doctor_id: int) -> User:
        return get_object_or_404(User, id=doctor_id, groups__name="Doctor")

    @extend_schema(
        tags=["Schedules"],
        summary="Update single doctor day schedule",
        description="Updates one doctor schedule day. Returns 404 when no entry exists for the given day.",
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="Doctor user ID.",
            ),
            OpenApiParameter(
                name="day",
                type=int,
                location=OpenApiParameter.PATH,
                description="Day of week (0-6).",
            ),
        ],
        request=DoctorScheduleDayUpdateSerializer,
        responses={200: DoctorScheduleSerializer},
    )
    def put(self, request, id: int, day: int):
        doctor = self._get_doctor(id)
        schedule = get_object_or_404(DoctorSchedule, doctor=doctor, day_of_week=day)

        serializer = DoctorScheduleDayUpdateSerializer(schedule, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(DoctorScheduleSerializer(schedule).data, status=status.HTTP_200_OK)


class DoctorScheduleExceptionListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrReceptionist]

    def _get_doctor(self, doctor_id: int) -> User:
        return get_object_or_404(User, id=doctor_id, groups__name="Doctor")

    @extend_schema(
        tags=["Schedules"],
        summary="List doctor schedule exceptions",
        description="Returns all schedule exceptions for a specific doctor.",
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="Doctor user ID.",
            )
        ],
        responses={200: ScheduleExceptionSerializer(many=True)},
    )
    def get(self, request, id: int):
        doctor = self._get_doctor(id)
        queryset = ScheduleException.objects.filter(doctor=doctor).order_by("-start_date", "id")
        serializer = ScheduleExceptionSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Schedules"],
        summary="Create doctor schedule exception",
        description=(
            "Creates a schedule exception for a doctor. "
            "`exception_type` enum: `day_off` or `one_off`."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="Doctor user ID.",
            )
        ],
        request=ScheduleExceptionCreateSerializer,
        responses={201: ScheduleExceptionSerializer, 400: MessageResponseSerializer},
    )
    def post(self, request, id: int):
        doctor = self._get_doctor(id)
        serializer = ScheduleExceptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(doctor=doctor)
        return Response(ScheduleExceptionSerializer(instance).data, status=status.HTTP_201_CREATED)


class DoctorScheduleExceptionDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrReceptionist]

    def _get_doctor(self, doctor_id: int) -> User:
        return get_object_or_404(User, id=doctor_id, groups__name="Doctor")

    @extend_schema(
        tags=["Schedules"],
        summary="Delete doctor schedule exception",
        description="Deletes one schedule exception by its ID for the given doctor.",
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="Doctor user ID.",
            ),
            OpenApiParameter(
                name="exception_id",
                type=int,
                location=OpenApiParameter.PATH,
                description="Schedule exception ID.",
            ),
        ],
        responses={204: None, 404: MessageResponseSerializer},
    )
    def delete(self, request, id: int, exception_id: int):
        doctor = self._get_doctor(id)
        exception = get_object_or_404(ScheduleException, id=exception_id, doctor=doctor)
        exception.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
