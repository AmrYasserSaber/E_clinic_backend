from rest_framework.permissions import BasePermission


class IsApproved(BasePermission):
    """Reject authenticated but non-approved users (doctors/receptionists pending admin approval)."""

    message = "Your account is pending approval."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return True
        return bool(getattr(user, "is_approved", True))


class IsAdmin(BasePermission):
    """Allow access only to users in the Admin group."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.groups.filter(name="Admin").exists())


class IsDoctor(BasePermission):
    """Allow access only to users in the Doctor group."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.groups.filter(name="Doctor").exists())


class IsReceptionist(BasePermission):
    """Allow access only to users in the Receptionist group."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.groups.filter(name="Receptionist").exists())


class IsPatient(BasePermission):
    """Allow access only to users in the Patient group."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.groups.filter(name="Patient").exists())

