from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group


class Command(BaseCommand):
    help = "Create the Patron and Librarian groups"

    def handle(self, *args, **options):
        librarian_group, _ = Group.objects.get_or_create(name="Librarian")
        patron_group, _ = Group.objects.get_or_create(name="Patron")
        print("Groups created.")
