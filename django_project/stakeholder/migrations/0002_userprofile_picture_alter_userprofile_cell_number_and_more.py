# Generated by Django 4.1.7 on 2023-06-11 21:16

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("stakeholder", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="picture",
            field=models.ImageField(
                blank=True, null=True, upload_to="profile_pictures"
            ),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="cell_number",
            field=models.CharField(blank=True, default="", max_length=15, null=True),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="user",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="user_profile",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
