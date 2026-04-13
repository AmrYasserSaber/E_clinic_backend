# Fixes DB drift: 0002 replaced Appointment and dropped dependent tables; 0003 did not
# recreate AppointmentAuditLog, RescheduleHistory, ConsultationRecord, PrescriptionItem.

from django.db import connection, migrations


def ensure_related_tables(apps, schema_editor):
    existing = set(connection.introspection.table_names())
    for model_name in (
        "RescheduleHistory",
        "AppointmentAuditLog",
        "ConsultationRecord",
        "PrescriptionItem",
    ):
        model = apps.get_model("appointments", model_name)
        table = model._meta.db_table
        if table not in existing:
            schema_editor.create_model(model)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0003_align_appointment_with_model"),
    ]

    operations = [
        migrations.RunPython(ensure_related_tables, noop_reverse),
    ]
