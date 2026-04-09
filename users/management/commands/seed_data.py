from __future__ import annotations

from datetime import date

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from users.models import User


class Command(BaseCommand):
    help = "Seed initial users and group assignments."

    def handle(self, *args, **options) -> None:
        self._seed_admin()
        self._seed_doctors()
        self._seed_receptionist()
        self._seed_patients()
        self.stdout.write(self.style.SUCCESS("Seed data created/verified."))

    def _seed_admin(self) -> None:
        self._create_user_if_missing(
            email="admin@eclinic.com",
            password="Test@123",
            first_name="System",
            last_name="Admin",
            phone_number="01012345678",
            date_of_birth=date(1990, 1, 1),
            is_staff=True,
            is_superuser=True,
            is_approved=True,
            group_name="Admin",
        )

    def _seed_doctors(self) -> None:
        self._create_user_if_missing(
            email="dr.ahmed@eclinic.com",
            password="Test@123",
            first_name="Ahmed",
            last_name="Hassan",
            phone_number="01112345678",
            date_of_birth=date(1987, 5, 12),
            is_approved=True,
            group_name="Doctor",
        )
        self._create_user_if_missing(
            email="dr.sara@eclinic.com",
            password="Test@123",
            first_name="Sara",
            last_name="Mostafa",
            phone_number="01212345678",
            date_of_birth=date(1991, 9, 3),
            is_approved=True,
            group_name="Doctor",
        )

    def _seed_receptionist(self) -> None:
        self._create_user_if_missing(
            email="reception@eclinic.com",
            password="Test@123",
            first_name="Mona",
            last_name="Ali",
            phone_number="01512345678",
            date_of_birth=date(1995, 2, 20),
            is_approved=True,
            group_name="Receptionist",
        )

    def _seed_patients(self) -> None:
        self._create_user_if_missing(
            email="patient1@eclinic.com",
            password="Test@123",
            first_name="Omar",
            last_name="Nabil",
            phone_number="01023456789",
            date_of_birth=date(2000, 7, 8),
            is_approved=True,
            group_name="Patient",
        )
        self._create_user_if_missing(
            email="patient2@eclinic.com",
            password="Test@123",
            first_name="Nour",
            last_name="Adel",
            phone_number="01123456789",
            date_of_birth=date(2002, 11, 15),
            is_approved=True,
            group_name="Patient",
        )
        self._create_user_if_missing(
            email="patient3@eclinic.com",
            password="Test@123",
            first_name="Youssef",
            last_name="Said",
            phone_number="01223456789",
            date_of_birth=date(1999, 4, 25),
            is_approved=True,
            group_name="Patient",
        )

    def _create_user_if_missing(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        phone_number: str,
        date_of_birth: date,
        is_approved: bool,
        group_name: str,
        is_staff: bool = False,
        is_superuser: bool = False,
    ) -> None:
        if User.objects.filter(email=email).exists():
            return
        user: User = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            date_of_birth=date_of_birth,
            is_active=True,
            is_staff=is_staff,
            is_superuser=is_superuser,
            is_approved=is_approved,
        )
        group: Group = Group.objects.get(name=group_name)
        user.groups.add(group)

