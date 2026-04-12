import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def forwards_status(apps, schema_editor):
    Appointment = apps.get_model("appointments", "Appointment")
    mapping = {
        "requested": "REQUESTED",
        "confirmed": "CONFIRMED",
        "checked_in": "CHECKED_IN",
        "completed": "COMPLETED",
        "cancelled": "CANCELLED",
        "no_show": "NO_SHOW",
    }
    for row in Appointment.objects.all().iterator():
        new_status = mapping.get(row.status, row.status)
        if new_status != row.status:
            row.status = new_status
            row.save(update_fields=["status"])


def backwards_status(apps, schema_editor):
    Appointment = apps.get_model("appointments", "Appointment")
    mapping = {
        "REQUESTED": "requested",
        "CONFIRMED": "confirmed",
        "CHECKED_IN": "checked_in",
        "COMPLETED": "completed",
        "CANCELLED": "cancelled",
        "NO_SHOW": "no_show",
    }
    for row in Appointment.objects.all().iterator():
        old_status = mapping.get(row.status, row.status)
        if old_status != row.status:
            row.status = old_status
            row.save(update_fields=["status"])


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0002_rebuild_appointment_model"),
        ("slots", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="appointment",
            options={"ordering": ["-appointment_date", "-appointment_time", "-id"]},
        ),
        migrations.AlterUniqueTogether(
            name="appointment",
            unique_together=set(),
        ),
        migrations.RenameField(
            model_name="appointment",
            old_name="date",
            new_name="appointment_date",
        ),
        migrations.RenameField(
            model_name="appointment",
            old_name="time",
            new_name="appointment_time",
        ),
        migrations.RenameField(
            model_name="appointment",
            old_name="session_duration",
            new_name="session_duration_minutes",
        ),
        migrations.AlterField(
            model_name="appointment",
            name="session_duration_minutes",
            field=models.PositiveSmallIntegerField(default=30),
        ),
        migrations.RunPython(forwards_status, backwards_status),
        migrations.AlterField(
            model_name="appointment",
            name="status",
            field=models.CharField(
                choices=[
                    ("REQUESTED", "Requested"),
                    ("CONFIRMED", "Confirmed"),
                    ("CHECKED_IN", "Checked In"),
                    ("COMPLETED", "Completed"),
                    ("CANCELLED", "Cancelled"),
                    ("NO_SHOW", "No Show"),
                ],
                default="REQUESTED",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="appointment",
            name="reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="appointment",
            name="slot",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="appointments",
                to="slots.slot",
            ),
        ),
        migrations.AlterField(
            model_name="appointment",
            name="doctor",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="doctor_appointments",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="appointment",
            name="patient",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="patient_appointments",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(
                fields=["patient", "appointment_date"],
                name="appointment_patient_8037cd_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(
                fields=["doctor", "appointment_date"],
                name="appointment_doctor__4d4b79_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(fields=["status"], name="appointment_status_8fe9d7_idx"),
        ),
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(
                fields=["appointment_date", "appointment_time"],
                name="appointment_appoint_c5b816_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="appointment",
            constraint=models.UniqueConstraint(
                fields=("doctor", "appointment_date", "appointment_time"),
                name="uniq_appointment_doctor_date_time",
            ),
        ),
        migrations.AlterField(
            model_name="appointment",
            name="appointment_date",
            field=models.DateField(),
        ),
        migrations.AlterField(
            model_name="appointment",
            name="appointment_time",
            field=models.TimeField(),
        ),
    ]
