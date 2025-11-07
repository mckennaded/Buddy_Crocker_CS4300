import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist

User = get_user_model()

class Command(BaseCommand):
    help = 'Create superuser from environment variables if not exists'

    def handle(self, *args, **kwargs):
        username = os.getenv('DJANGO_SUPERUSER_USERNAME')
        email = os.getenv('DJANGO_SUPERUSER_EMAIL')
        password = os.getenv('DJANGO_SUPERUSER_PASSWORD')

        if not username or not email or not password:
            self.stderr.write(self.style.ERROR(
                "Missing environment variables. Please set DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, and DJANGO_SUPERUSER_PASSWORD"))
            return

        try:
            user = User.objects.get(username=username)
            if user.is_superuser:
                self.stdout.write(self.style.SUCCESS(
                    f"Superuser '{username}' already exists."))
            else:
                self.stderr.write(self.style.WARNING(
                    f"User '{username}' exists but is not a superuser."))
        except ObjectDoesNotExist:
            User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(
                f"Superuser '{username}' created successfully."))
