from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0002_rebuild_appointment_model"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="reason",
            field=models.TextField(blank=True),
        ),
    ]
