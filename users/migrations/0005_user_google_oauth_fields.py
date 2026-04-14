from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_user_specialty"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="google_sub",
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="user",
            name="google_email",
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="google_linked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

