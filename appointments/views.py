from __future__ import annotations

import datetime as dt
from datetime import date
from itertools import groupby

from django.contrib.auth import get_user_model
from django.db.models import Case, IntegerField, Q, Value, When
from django.db.models.functions import Concat
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from appointments.models import Appointment, AppointmentStatus
from appointments.serializers import (
    AppointmentBookingSerializer,
    AppointmentDeclineSerializer,
    AppointmentRescheduleSerializer,
    AppointmentSerializer,
    AvailableSlotSerializer,
    ConsultationCreateSerializer,
    DoctorQueueItemSerializer,
    DoctorSlotSerializer,
    ReceptionistAppointmentSerializer,
)
from appointments.services import (
    BookingConflictError,
    cancel_appointment,
    check_in_appointment,
    confirm_appointment,
    decline_appointment,
    ensure_object_access,
    file_consultation,
    get_appointment_for_access_check,
    get_appointment_for_list_queryset,
    get_primary_role,
    mark_no_show,
    reschedule_appointment,
    scope_queryset_for_user,
)
from appointments.slot_generation import iter_available_slots
from slots.models import Slot
from users.permissions import IsApproved, IsDoctor

User = get_user_model()

ORDERING_WHITELIST = {
    "appointment_date",
    "-appointment_date",
    "appointment_time",
    "-appointment_time",
    "status",
    "-status",
    "created_at",
    "-created_at",
    "updated_at",
    "-updated_at",
    "check_in_time",
    "-check_in_time",
}


def _parse_iso_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({field_name: f"Invalid {field_name}. Expected YYYY-MM-DD."}) from exc


def _get_response_serializer(role: str):
    if role == "Receptionist":
        return ReceptionistAppointmentSerializer
    return AppointmentSerializer


def _apply_query_filters(*, queryset, request, role: str):
    status_value = request.query_params.get("status")
    date_from = request.query_params.get("date_from")
    date_to = request.query_params.get("date_to")
    doctor_id = request.query_params.get("doctor_id")
    patient_id = request.query_params.get("patient_id")
    search_term = request.query_params.get("search")
    ordering = request.query_params.get("ordering")

    if status_value:
        normalized_status = status_value.upper()
        valid_statuses = {status for status, _ in AppointmentStatus.choices}
        if normalized_status not in valid_statuses:
            raise ValidationError({"status": "Invalid status filter value."})
        queryset = queryset.filter(status=normalized_status)

    if date_from:
        queryset = queryset.filter(
            appointment_date__gte=_parse_iso_date(date_from, "date_from")
        )

    if date_to:
        queryset = queryset.filter(
            appointment_date__lte=_parse_iso_date(date_to, "date_to")
        )

    if doctor_id is not None:
        if role == "Patient":
            raise PermissionDenied("doctor_id filter is staff-only.")
        if role == "Doctor" and str(request.user.id) != str(doctor_id):
            raise PermissionDenied("Doctors can only filter by their own doctor_id.")
        queryset = queryset.filter(doctor_id=doctor_id)

    if patient_id is not None:
        if role == "Patient":
            raise PermissionDenied("patient_id filter is staff-only.")
        queryset = queryset.filter(patient_id=patient_id)

    if search_term:
        if role == "Patient":
            raise PermissionDenied("search is staff-only.")

        search_term = search_term.strip()
        queryset = queryset.annotate(
            patient_full_name=Concat(
                "patient__first_name",
                Value(" "),
                "patient__last_name",
            )
        )
        search_predicate = Q(patient_full_name__icontains=search_term)
        if search_term.isdigit():
            search_predicate |= Q(id=int(search_term))
        queryset = queryset.filter(search_predicate)

    if ordering:
        requested_fields = [item.strip() for item in ordering.split(",") if item.strip()]
        invalid_fields = [field for field in requested_fields if field not in ORDERING_WHITELIST]
        if invalid_fields:
            raise ValidationError(
                {"ordering": f"Invalid ordering fields: {', '.join(invalid_fields)}."}
            )
        queryset = queryset.order_by(*requested_fields)
    else:
        queryset = queryset.order_by("-appointment_date", "-appointment_time", "-id")

    return queryset


class AppointmentListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsApproved]

    def get(self, request):
        queryset = get_appointment_for_list_queryset()
        scoped_queryset, role = scope_queryset_for_user(queryset, request.user)
        filtered_queryset = _apply_query_filters(
            queryset=scoped_queryset,
            request=request,
            role=role,
        )
        serializer_class = _get_response_serializer(role)
        serializer = serializer_class(filtered_queryset, many=True, context={"request": request})
        return Response(serializer.data, status=200)

    def post(self, request):
        role = get_primary_role(request.user)
        if role != "Patient":
            raise PermissionDenied("Only patients can create appointments.")

        booking_serializer = AppointmentBookingSerializer(data=request.data)
        booking_serializer.is_valid(raise_exception=True)

        try:
            appointment = booking_serializer.save(patient=request.user)
        except BookingConflictError as exc:
            return Response({"detail": str(exc)}, status=409)

        serializer = AppointmentSerializer(appointment, context={"request": request})
        return Response(serializer.data, status=201)


class AppointmentDetailView(APIView):
    permission_classes = [IsAuthenticated, IsApproved]

    def get(self, request, pk: int):
        appointment = get_appointment_for_access_check(pk)
        ensure_object_access(user=request.user, appointment=appointment)

        role = get_primary_role(request.user)
        serializer_class = _get_response_serializer(role)
        serializer = serializer_class(appointment, context={"request": request})
        return Response(serializer.data, status=200)


class AppointmentCancelView(APIView):
    permission_classes = [IsAuthenticated, IsApproved]

    def patch(self, request, pk: int):
        appointment = cancel_appointment(appointment_id=pk, actor=request.user)
        role = get_primary_role(request.user)
        serializer_class = _get_response_serializer(role)
        return Response(serializer_class(appointment, context={"request": request}).data, status=200)


class AppointmentConfirmView(APIView):
    permission_classes = [IsAuthenticated, IsApproved]

    def patch(self, request, pk: int):
        appointment = confirm_appointment(appointment_id=pk, actor=request.user)
        role = get_primary_role(request.user)
        serializer_class = _get_response_serializer(role)
        return Response(serializer_class(appointment, context={"request": request}).data, status=200)


class AppointmentDeclineView(APIView):
    permission_classes = [IsAuthenticated, IsApproved]

    def patch(self, request, pk: int):
        payload = AppointmentDeclineSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        appointment = decline_appointment(
            appointment_id=pk,
            actor=request.user,
            reason=payload.validated_data.get("reason", ""),
        )
        role = get_primary_role(request.user)
        serializer_class = _get_response_serializer(role)
        return Response(serializer_class(appointment, context={"request": request}).data, status=200)


class AppointmentCheckInView(APIView):
    permission_classes = [IsAuthenticated, IsApproved]

    def patch(self, request, pk: int):
        appointment = check_in_appointment(
            appointment_id=pk,
            actor=request.user,
            client_sent_check_in_time="check_in_time" in request.data,
        )
        role = get_primary_role(request.user)
        serializer_class = _get_response_serializer(role)
        return Response(serializer_class(appointment, context={"request": request}).data, status=200)


class AppointmentNoShowView(APIView):
    permission_classes = [IsAuthenticated, IsApproved]

    def patch(self, request, pk: int):
        appointment = mark_no_show(appointment_id=pk, actor=request.user)
        role = get_primary_role(request.user)
        serializer_class = _get_response_serializer(role)
        return Response(serializer_class(appointment, context={"request": request}).data, status=200)


class AppointmentRescheduleView(APIView):
    permission_classes = [IsAuthenticated, IsApproved]

    def patch(self, request, pk: int):
        payload = AppointmentRescheduleSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        vd = payload.validated_data
        kwargs = {
            "appointment_id": pk,
            "actor": request.user,
            "reason": vd.get("reason", ""),
        }
        if vd.get("new_slot_id") is not None:
            kwargs["new_slot_id"] = vd["new_slot_id"]
        else:
            kwargs["doctor_id"] = vd["doctor_id"]
            kwargs["appointment_date"] = vd["appointment_date"]
            kwargs["appointment_time"] = vd["appointment_time"]

        try:
            appointment = reschedule_appointment(**kwargs)
        except BookingConflictError as exc:
            return Response({"detail": str(exc)}, status=409)

        role = get_primary_role(request.user)
        serializer_class = _get_response_serializer(role)
        return Response(serializer_class(appointment, context={"request": request}).data, status=200)


class DoctorMyScheduleView(APIView):
    permission_classes = [IsAuthenticated, IsApproved, IsDoctor]

    @extend_schema(tags=["doctors"])
    def get(self, request):
        slots = (
            Slot.objects.filter(doctor=request.user)
            .order_by("date", "start_time", "id")
        )

        grouped_items = []
        for slot_date, slot_group in groupby(slots, key=lambda item: item.date):
            serialized_slots = DoctorSlotSerializer(slot_group, many=True).data
            grouped_items.append({"date": slot_date, "slots": serialized_slots})

        return Response({"items": grouped_items}, status=200)


class DoctorMyQueueView(APIView):
    permission_classes = [IsAuthenticated, IsApproved, IsDoctor]

    @extend_schema(tags=["doctors"])
    def get(self, request):
        date_param = request.query_params.get("date")
        if date_param:
            target_date = _parse_iso_date(date_param, "date")
        else:
            target_date = timezone.localdate()

        queue_queryset = (
            Appointment.objects.select_related("patient")
            .filter(
                doctor=request.user,
                appointment_date=target_date,
                status__in=[AppointmentStatus.CHECKED_IN, AppointmentStatus.CONFIRMED],
            )
            .annotate(
                queue_priority=Case(
                    When(status=AppointmentStatus.CHECKED_IN, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            )
            .order_by("queue_priority", "check_in_time", "appointment_time", "id")
        )

        serializer = DoctorQueueItemSerializer(queue_queryset, many=True)
        return Response({"date": target_date, "items": serializer.data}, status=200)


class AppointmentConsultationCreateView(APIView):
    permission_classes = [IsAuthenticated, IsApproved, IsDoctor]

    @extend_schema(tags=["doctors"])
    def post(self, request, pk: int):
        payload = ConsultationCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        appointment = file_consultation(
            appointment_id=pk,
            actor=request.user,
            diagnosis=payload.validated_data["diagnosis"],
            notes=payload.validated_data.get("notes", ""),
            requested_tests=payload.validated_data.get("requested_tests", []),
            prescription_items=payload.validated_data.get("prescription_items", []),
        )

        serializer = AppointmentSerializer(appointment, context={"request": request})
        return Response(serializer.data, status=201)


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