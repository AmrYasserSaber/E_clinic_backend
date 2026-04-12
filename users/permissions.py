from __future__ import annotations

from rest_framework.permissions import BasePermission


class IsApproved(BasePermission):
    message = "Your account is pending approval."

    APPROVAL_REQUIRED_GROUPS = {"Doctor", "Receptionist"}

    @classmethod
    def may_receive_tokens(cls, user) -> bool:
        requires_approval = user.groups.filter(
            name__in=cls.APPROVAL_REQUIRED_GROUPS
        ).exists()
        if not requires_approval:
            return True
        return bool(getattr(user, "is_approved", False))

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return True
        return self.may_receive_tokens(user)


class GroupPermission(BasePermission):
    required_group: str | None = None
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if not self.required_group:
            return False
        return user.groups.filter(name=self.required_group).exists()


class IsAdmin(GroupPermission):
    required_group = "Admin"


class IsDoctor(GroupPermission):
    required_group = "Doctor"


class IsReceptionist(GroupPermission):
    required_group = "Receptionist"


class IsPatient(GroupPermission):
    required_group = "Patient"


class IsAdminOrDoctor(BasePermission):
    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.groups.filter(name__in=["Admin", "Doctor"]).exists()
        )


class IsAdminOrDoctorOrReceptionist(BasePermission):
    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.groups.filter(
                name__in=["Admin", "Doctor", "Receptionist"]
            ).exists()
        )
