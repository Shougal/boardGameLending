from allauth.socialaccount.signals import (
    pre_social_login,
    # social_account_added,
    # social_account_updated
)
from allauth.account.signals import user_signed_up
from django.dispatch import receiver
from django.contrib.auth.models import Group


@receiver(pre_social_login)
def handle_pre_social_login(sender, request, sociallogin, **kwargs):
    user = sociallogin.user
    extra_data = sociallogin.account.extra_data

    # Populate user fields from Google data
    user.given_name = extra_data.get("given_name", "")
    user.family_name = extra_data.get("family_name", "")

    print(
        f"[INFO] Social account information associated with user model for user {user.given_name} {user.family_name}."
    )


"""
@receiver([social_account_added, social_account_updated])
def handle_social_account_added(sender, request, sociallogin, **kwargs):
    user = sociallogin.user
    extra_data = sociallogin.account.extra_data

    # Populate user fields from Google data
    user.given_name = extra_data.get("given_name", "")
    user.family_name = extra_data.get("family_name", "")
    patron_group, _ = Group.objects.get_or_create(name="Patron")
    user.groups.add(patron_group)

    print(f"[INFO] User {user.given_name} {user.family_name} added to Patron group.")
"""


@receiver(user_signed_up)
def user_signed_up_handler(request, user, **kwargs):
    # Check if social data is provided
    sociallogin = kwargs.get("sociallogin")
    if sociallogin:
        extra_data = sociallogin.account.extra_data
        user.given_name = extra_data.get("given_name", "")
        user.family_name = extra_data.get("family_name", "")

    # Add the user to the Patron group
    patron_group, _ = Group.objects.get_or_create(name="Patron")
    user.groups.add(patron_group)
    user.save()

    print(
        f"[INFO] New user {user.given_name} {user.family_name} signed up and added to Patron group."
    )
