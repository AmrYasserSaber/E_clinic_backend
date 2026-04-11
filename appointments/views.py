from __future__ import annotations

from datetime import date

from django.db.models import Q, Value
from django.db.models.functions import Concat
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
    ReceptionistAppointmentSerializer,
)
from appointments.services import (
    BookingConflictError,
    cancel_appointment,
    check_in_appointment,
    confirm_appointment,
    decline_appointment,
    ensure_object_access,
    get_appointment_for_access_check,
    get_appointment_for_list_queryset,
    get_primary_role,
    mark_no_show,
    reschedule_appointment,
    scope_queryset_for_user,
)
from users.permissions import IsApproved


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
        queryset = queryset.filter(appointment_date__gte=_parse_iso_date(date_from, "date_from"))

    if date_to:
        queryset = queryset.filter(appointment_date__lte=_parse_iso_date(date_to, "date_to"))

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
                {
                    "ordering": f"Invalid ordering fields: {', '.join(invalid_fields)}."
                }
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

        try:
            appointment = reschedule_appointment(
                appointment_id=pk,
                actor=request.user,
                new_slot_id=payload.validated_data["new_slot_id"],
                reason=payload.validated_data.get("reason", ""),
            )
        except BookingConflictError as exc:
            return Response({"detail": str(exc)}, status=409)

        role = get_primary_role(request.user)
        serializer_class = _get_response_serializer(role)
        return Response(serializer_class(appointment, context={"request": request}).data, status=200)
