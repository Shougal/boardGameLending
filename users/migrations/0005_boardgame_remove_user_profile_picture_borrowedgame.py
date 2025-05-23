# Generated by Django 5.1.6 on 2025-03-15 05:01

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_alter_user_profile_picture"),
    ]

    operations = [
        migrations.CreateModel(
            name="BoardGame",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                (
                    "image",
                    models.ImageField(blank=True, null=True, upload_to="board-games/"),
                ),
            ],
        ),
        migrations.RemoveField(
            model_name="user",
            name="profile_picture",
        ),
        migrations.CreateModel(
            name="BorrowedGame",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("borrowed_on", models.DateTimeField(auto_now_add=True)),
                ("due_date", models.DateTimeField()),
                (
                    "game",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="borrowed_instances",
                        to="users.boardgame",
                    ),
                ),
                (
                    "lender",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lent_games",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="borrowed_games",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
