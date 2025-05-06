from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


class CustomUserAdmin(UserAdmin):
    model = User
    list_display = (
        "email",
        "given_name",
        "family_name",
        "is_librarian",
        "is_staff",
        "is_superuser",
    )
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Info", {"fields": ("given_name", "family_name")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "given_name",
                    "family_name",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )
    search_fields = ("email", "given_name", "family_name")
    ordering = ("email",)


admin.site.register(User, CustomUserAdmin)
