from __future__ import annotations

from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def create_rbac_groups(sender, **kwargs) -> None:
    users_app_config = apps.get_app_config("users")
    if sender.label != users_app_config.label:
        return
    admin_group, _ = Group.objects.get_or_create(name="Admin")
    doctor_group, _ = Group.objects.get_or_create(name="Doctor")
    receptionist_group, _ = Group.objects.get_or_create(name="Receptionist")
    patient_group, _ = Group.objects.get_or_create(name="Patient")
    all_permissions = Permission.objects.all()
    admin_group.permissions.set(all_permissions)
    view_users_permission = Permission.objects.filter(codename="view_users")
    create_users_permission = Permission.objects.filter(codename="create_users")
    manage_appointments_permission = Permission.objects.filter(codename="manage_appointments")
    doctor_group.permissions.set(list(view_users_permission) + list(manage_appointments_permission))
    receptionist_group.permissions.set(list(view_users_permission) + list(create_users_permission))
    patient_group.permissions.clear()
