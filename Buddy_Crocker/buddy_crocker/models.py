"""
Models for Buddy Crocker meal planning and recipe management app.

This module defines the core data models for managing allergens, ingredients,
recipes, user pantries, and user profiles.
"""
from datetime import timedelta
from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs): # pylint: disable=unused-argument
    """
    Creates new user profile
    """
    if created:
        # full_name = instance.get_full_name()
        Profile.objects.create(user=instance)

class Allergen(models.Model):
    """
    Represents a food allergen (e.g., peanuts, dairy, gluten).
    
    Attributes:
        name: Unique name of the allergen
        category: Classification (FDA Major 9, Dietary Preference, Custom)
        alternative_names: JSON list of synonyms for matching
        description: Detailed information about the allergen
        usda_search_terms: JSON list of keywords for USDA API matching
    """
    CATEGORY_CHOICES = [
        ('fda_major_9', 'FDA Major 9'),
        ('dietary_preference', 'Dietary Preference'),
        ('custom', 'Custom User-Added'),
    ]

    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default='custom'
    )
    alternative_names = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True)
    usda_search_terms = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        """Return the allergen name as string representation."""
        return self.name


class Ingredient(models.Model):
    """
    Represents a food ingredient with nutritional and allergen information.
    
    Attributes:
        name: Name of the ingredient (e.g., "Peanut Butter")
        brand: Brand name (e.g., "Jif", "Skippy") or "Generic"
        calories: Caloric content per standard serving
        allergens: Many-to-many relationship with allergens
    
    Note: The combination of name + brand must be unique
    """
    name = models.CharField(max_length=100)
    brand = models.CharField(max_length=100, default='Generic', blank=True)
    calories = models.PositiveIntegerField()
    allergens = models.ManyToManyField(
        Allergen,
        blank=True,
        related_name='ingredients'
    )

    def __str__(self):
        """Return the ingredient name with brand as string representation."""
        if self.brand and self.brand != 'Generic':
            return f"{self.name} ({self.brand})"
        return self.name

    class Meta:
        ordering = ['name', 'brand']
        unique_together = [['name', 'brand']]
        indexes = [
            models.Index(fields=['name', 'brand']),
        ]


class Recipe(models.Model):
    """
    Represents a recipe created by a user.
    
    Attributes:
        title: Recipe title
        author: User who created the recipe
        ingredients: Many-to-many relationship with ingredients
        instructions: Step-by-step cooking instructions
    """
    title = models.CharField(max_length=200)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    ingredients = models.ManyToManyField(Ingredient, related_name='recipes')
    instructions = models.TextField()
    created_date = models.DateField(auto_now_add=True)

    def __str__(self):
        """Return the recipe title and author as string representation."""
        return f"{self.title} by {self.author.username}"

    class Meta:
        unique_together = ('title', 'author')
        ordering = ['-id']  # Most recent first

    def get_allergens(self):
        """
        Get all allergens present in this recipe's ingredients.
        
        Returns:
            QuerySet of Allergen objects
        """
        return Allergen.objects.filter(
            ingredients__recipes=self
        ).distinct()


class Pantry(models.Model):
    """
    Represents a user's pantry containing available ingredients.
    
    Attributes:
        user: One-to-one relationship with User
        ingredients: Many-to-many relationship with ingredients
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    ingredients = models.ManyToManyField(
        Ingredient,
        blank=True,
        related_name='pantries'
    )

    def __str__(self):
        """Return the pantry owner's username as string representation."""
        return f"{self.user.username}'s Pantry"

    class Meta:
        verbose_name_plural = "Pantries"


class Profile(models.Model):
    """
    Represents a user's profile with dietary restrictions.
    
    Attributes:
        user: One-to-one relationship with User
        allergens: Many-to-many relationship with allergens to avoid
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    allergens = models.ManyToManyField(
        Allergen,
        blank=True,
        related_name='profiles'
    )

    def __str__(self):
        """Return the profile owner's username as string representation."""
        return f"{self.user.username}'s Profile"

    def get_safe_recipes(self):
        """
        Get recipes that don't contain any of the user's allergens.
        
        Returns:
            QuerySet of Recipe objects safe for this user
        """
        if not self.allergens.exists():
            return Recipe.objects.all()

        # Get recipes that contain ingredients with user's allergens
        unsafe_recipes = Recipe.objects.filter(
            ingredients__allergens__in=self.allergens.all()
        ).distinct()

        # Exclude those from all recipes
        return Recipe.objects.exclude(id__in=unsafe_recipes)

class ScanRateLimit(models.Model):
    """
    Track pantry scan attempts for rate limiting.
    
    Attributes:
        user: User who performed the scan
        timestamp: When the scan occurred
        ip_address: IP address of the request (optional backup identifier)
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='scan_attempts'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.timestamp}"

    @classmethod
    def check_rate_limit(cls, user, max_scans=5, time_window_minutes=5):
        """
        Check if user has exceeded rate limit.
        
        Args:
            user: User to check
            max_scans: Maximum scans allowed in time window
            time_window_minutes: Time window in minutes
            
        Returns:
            tuple: (is_allowed: bool, scans_remaining: int, reset_time: datetime)
        """
        cutoff_time = timezone.now() - timedelta(minutes=time_window_minutes)
        recent_scans = cls.objects.filter(
            user=user,
            timestamp__gte=cutoff_time
        ).count()

        is_allowed = recent_scans < max_scans
        scans_remaining = max(0, max_scans - recent_scans)

        # Calculate when the oldest scan will expire
        oldest_scan = cls.objects.filter(
            user=user,
            timestamp__gte=cutoff_time
        ).order_by('timestamp').first()

        reset_time = None
        if oldest_scan and not is_allowed:
            reset_time = oldest_scan.timestamp + timedelta(minutes=time_window_minutes)

        return is_allowed, scans_remaining, reset_time

    @classmethod
    def record_scan(cls, user, ip_address=None):
        """
        Record a scan attempt.
        
        Args:
            user: User performing the scan
            ip_address: Optional IP address
            
        Returns:
            ScanRateLimit instance
        """
        return cls.objects.create(user=user, ip_address=ip_address)

    @classmethod
    def cleanup_old_records(cls, days=7):
        """
        Remove scan records older than specified days.
        
        Args:
            days: Number of days to keep records
            
        Returns:
            int: Number of records deleted
        """
        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_count, _ = cls.objects.filter(timestamp__lt=cutoff_date).delete()
        return deleted_count
