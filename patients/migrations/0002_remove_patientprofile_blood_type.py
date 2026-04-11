from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("patients", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="patientprofile",
            name="blood_type",
        ),
    ]
