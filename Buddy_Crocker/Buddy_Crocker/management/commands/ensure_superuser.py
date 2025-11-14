"""
Django management command to ensure a superuser exists during application initialization.
"""

import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist

User = get_user_model()

class Command(BaseCommand):
    """Django management command to ensure a superuser exists.
    
    Creates a superuser from environment variables if it does not already exist.
    Environment variables used:
        - DJANGO_SUPERUSER_USERNAME: The username for the superuser
        - DJANGO_SUPERUSER_EMAIL: The email address for the superuser
        - DJANGO_SUPERUSER_PASSWORD: The password for the superuser
    
    This command is typically used during application initialization (e.g., in Docker
    startup scripts or CI/CD pipelines) to automatically provision the initial admin user.
    """
    help = 'Create superuser from environment variables if not exists'

    def handle(self, *args, **kwargs):
        """Execute the command to create or verify the superuser.
        
        Retrieves superuser credentials from environment variables and either:
        - Creates a new superuser if one does not exist
        - Logs success if a superuser with the given username already exists
        - Logs a warning if a user exists but is not a superuser
        - Logs an error if required environment variables are missing
        
        Args:
            *args: Variable length argument list (unused).
            **kwargs: Arbitrary keyword arguments (unused).
        
        Returns:
            None
        """
        username = os.getenv('DJANGO_SUPERUSER_USERNAME')
        email = os.getenv('DJANGO_SUPERUSER_EMAIL')
        password = os.getenv('DJANGO_SUPERUSER_PASSWORD')

        if not username or not email or not password:
            self.stderr.write(self.style.ERROR(
                "Missing environment variables. Please set DJANGO_SUPERUSER_USERNAME, "
                "DJANGO_SUPERUSER_EMAIL, and DJANGO_SUPERUSER_PASSWORD"
            ))
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
