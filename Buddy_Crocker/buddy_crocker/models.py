"""
Models for Buddy Crocker meal planning and recipe management app.

This module defines the core data models for managing allergens, ingredients,
recipes, user pantries, and user profiles.
"""

from datetime import timedelta
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):  # pylint: disable=unused-argument
    """Creates new user profile."""
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
        """Meta options for Allergen model."""
        ordering = ['name']

    def __str__(self):
        """Return the allergen name as string representation."""
        return str(self.name)


class Ingredient(models.Model):
    """
    Represents a food ingredient with nutritional and allergen information.

    Attributes:
        name: Name of the ingredient (e.g., "Peanut Butter")
        brand: Brand name (e.g., "Jif", "Skippy") or "Generic"
        calories: Caloric content per 100g (standard USDA measurement)
        allergens: Many-to-many relationship with allergens
        fdc_id: USDA FoodData Central ID (optional, for USDA-sourced ingredients)
        nutrition_data: JSON field storing complete nutrient breakdown
        portion_data: JSON field storing available serving sizes with gram weights
        last_updated: Timestamp of when USDA data was last fetched

    Note: The combination of name + brand must be unique
    """
    name = models.CharField(max_length=100)
    brand = models.CharField(max_length=100, default='Generic', blank=True)
    calories = models.PositiveIntegerField(
        help_text="Calories per 100g (USDA standard)"
    )
    allergens = models.ManyToManyField(
        Allergen,
        blank=True,
        related_name='ingredients'
    )

    # New fields for USDA data
    fdc_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="USDA FoodData Central ID"
    )
    nutrition_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Complete nutrient data from USDA (macros, vitamins, minerals)"
    )
    portion_data = models.JSONField(
        default=list,
        blank=True,
        help_text="Available serving sizes with gram weights from USDA"
    )
    last_updated = models.DateTimeField(
        auto_now=True,
        help_text="When nutrition/portion data was last updated"
    )

    def __str__(self):
        """Return the ingredient name with brand as string representation."""
        if self.brand and self.brand != 'Generic':
            return f"{self.name} ({self.brand})"
        return self.name

    class Meta:
        """Meta options for Ingredient model."""
        ordering = ['name', 'brand']
        unique_together = [['name', 'brand']]
        indexes = [
            models.Index(fields=['name', 'brand']),
            models.Index(fields=['fdc_id']),  # Index for USDA lookups
        ]

    def has_nutrition_data(self):
        """Check if ingredient has complete nutrition data."""
        return bool(self.nutrition_data)

    def has_portion_data(self):
        """Check if ingredient has portion/serving size data."""
        return bool(self.portion_data)

    def is_usda_sourced(self):
        """Check if ingredient came from USDA database."""
        return self.fdc_id is not None

    def get_nutrient(self, nutrient_key, category='macronutrients'):
        """
        Get a specific nutrient value from nutrition_data.

        Args:
            nutrient_key: Key like 'protein', 'vitamin_c', etc.
            category: 'macronutrients', 'vitamins', 'minerals', or 'other'

        Returns:
            Dictionary with nutrient info or None if not found
        """
        if not self.nutrition_data:
            return None

        category_data = self.nutrition_data.get(category, {})
        return category_data.get(nutrient_key)

    def get_portion_by_unit(self, unit_name):
        """
        Get portion data for a specific unit (e.g., 'cup', 'slice').

        Args:
            unit_name: Name of the measure unit

        Returns:
            Portion dictionary or None if not found
        """
        if not self.portion_data:
            return None

        for portion in self.portion_data:
            if portion.get('measure_unit', '').lower() == unit_name.lower():
                return portion

        return None


class RecipeIngredient(models.Model):
    """
    Through model for Recipe-Ingredient relationship with amounts and units.

    Stores specific amount and unit for each ingredient in a recipe,
    enabling calorie calculations and detailed recipe instructions.
    """
    recipe = models.ForeignKey(
        'Recipe',
        on_delete=models.CASCADE,
        related_name='recipe_ingredients'
    )
    ingredient = models.ForeignKey(
        'Ingredient',
        on_delete=models.CASCADE,
        related_name='ingredient_recipes'
    )

    # Amount and unit fields
    amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="Amount of ingredient (e.g., 2 for '2 cups')"
    )
    unit = models.CharField(
        max_length=50,
        help_text="Unit of measurement (e.g., cup, tsp, g, oz)"
    )

    # Store gram weight for calorie calculations
    gram_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Weight in grams for calorie calculation"
    )

    # Optional notes for this specific ingredient in recipe
    notes = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional notes (e.g., 'chopped', 'to taste')"
    )

    # Order for display
    order = models.PositiveIntegerField(
        default=0,
        help_text="Order of ingredient in recipe"
    )

    class Meta:
        """Meta options for RecipeIngredient model."""
        ordering = ['order', 'id']
        unique_together = [['recipe', 'ingredient']]

    def __str__(self):
        return f"{self.amount} {self.unit} {self.ingredient.name}"

    def calculate_calories(self):
        """
        Calculate calories for this ingredient amount.

        Returns:
            int: Calories for the specified amount
        """

        calories_per_100g = self.ingredient.calories

        # Return default 100g weight
        if not self.gram_weight:
            return 0

        # Return portioned calories if there is a portion
        return int((calories_per_100g * float(self.gram_weight)) / 100)

    def get_portion_gram_weight(self):
        """
        Get gram weight for this ingredient's portion from USDA data.

        Returns:
            float: Gram weight if found, None otherwise
        """
        if not self.ingredient.has_portion_data():
            return None

        portion = self.ingredient.get_portion_by_unit(self.unit)
        if portion:
            # Scale by amount
            return portion['gram_weight'] * float(self.amount)

        return None

    def auto_calculate_gram_weight(self):
        """
        Automatically calculate and set gram weight from USDA portion data.

        Returns:
            bool: True if successfully calculated, False otherwise
        """

        # Calculate if already in grams
        unit_lower = self.unit.lower().strip()
        if unit_lower in ['g']:
            self.gram_weight = float(self.amount)
            return True

        # Calculate non gram units
        calculated = self.get_portion_gram_weight()
        if calculated:
            self.gram_weight = calculated
            return True
        return False


class Recipe(models.Model):
    """
    Represents a recipe created by a user.

    Attributes:
        title: Recipe title
        author: User who created the recipe
        ingredients: Many-to-many relationship with ingredients
        instructions: Step-by-step cooking instructions
        created_date
        updated_date
        servings
        prep_time
        cook_time
        difficulty
        image
        placeholder_color: To set color of image placeholder
    """
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]

    title = models.CharField(max_length=200)
    author = models.ForeignKey(User, on_delete=models.CASCADE)

    # Updated M2M with through model
    ingredients = models.ManyToManyField(
        'Ingredient',
        through='RecipeIngredient',
        related_name='recipes'
    )

    instructions = models.TextField()
    created_date = models.DateField(auto_now_add=True)
    updated_date = models.DateField(auto_now=True)

    # New fields for servings and metadata
    servings = models.PositiveIntegerField(
        default=4,
        validators=[MinValueValidator(1)],
        help_text="Number of servings this recipe makes"
    )

    prep_time = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Preparation time in minutes"
    )

    cook_time = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Cooking time in minutes"
    )

    difficulty = models.CharField(
        max_length=10,
        choices=DIFFICULTY_CHOICES,
        default='medium',
        help_text="Recipe difficulty level"
    )

    # Recipe image
    image = models.ImageField(
        upload_to='recipe_images/',
        null=True,
        blank=True,
        help_text="Photo of the finished dish"
    )

    # For placeholder if no image
    placeholder_color = models.CharField(
        max_length=7,
        default='#0B63F2',
        help_text="Hex color for placeholder card"
    )

    class Meta:
        """Meta options for Recipe model."""
        unique_together = ('title', 'author')
        ordering = ['-created_date']

    def __str__(self):
        return f"{self.title} by {self.author.username}"

    def get_total_time(self):
        """Get total time (prep + cook) in minutes."""
        total = 0
        if self.prep_time:
            total += self.prep_time
        if self.cook_time:
            total += self.cook_time
        return total if total > 0 else None

    def calculate_total_calories(self):
        """
        Calculate total calories for entire recipe.

        Returns:
            int: Total calories for all ingredients
        """
        total = 0
        for recipe_ing in self.recipe_ingredients.all():
            total += recipe_ing.calculate_calories()
        return total

    def calculate_calories_per_serving(self):
        """
        Calculate calories per serving.

        Returns:
            int: Calories per serving (rounded)
        """
        total_calories = self.calculate_total_calories()
        if self.servings > 0:
            return int(total_calories / self.servings)
        return 0

    def get_allergens(self):
        """Get all allergens from recipe ingredients."""
        return Allergen.objects.filter(
            ingredients__recipes=self
        ).distinct()

    def get_ingredient_list(self):
        """
        Get formatted list of ingredients with amounts.

        Returns:
            list: List of RecipeIngredient objects ordered by order field
        """
        return self.recipe_ingredients.select_related('ingredient').all()

    def has_complete_nutrition_data(self):
        """Check if all ingredients have gram weights for calorie calculation."""
        return all(
            ri.gram_weight is not None
            for ri in self.recipe_ingredients.all()
        )


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
        """Meta options for Pantry model."""
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

    class Meta:
        """Meta options for Profile model."""

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


class ShoppingListItem(models.Model):
    """
    Represents an item on a user's shopping list.

    Attributes:
        user: Foreign key to User who owns this shopping list item
        ingredient: Optional foreign key to Ingredient model (for pantry integration)
        ingredient_name: Name of the ingredient/item to purchase
        quantity: Optional quantity/amount text (e.g., "2 cups", "1 lb")
        is_purchased: Boolean tracking if item has been purchased
        added_from_recipe: Optional foreign key tracking source recipe
        notes: Optional additional notes about the item
        created_at: Timestamp when item was added
        updated_at: Timestamp when item was last modified
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='shopping_list_items'
    )

    # Optional link to existing ingredient in database
    ingredient = models.ForeignKey(
        'Ingredient',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='shopping_list_items',
        help_text="Link to ingredient in database if applicable"
    )

    # Always store the name as text for flexibility
    ingredient_name = models.CharField(
        max_length=200,
        help_text="Name of ingredient or item to purchase"
    )

    quantity = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Amount needed (e.g., '2 cups', '500g')"
    )

    is_purchased = models.BooleanField(
        default=False,
        help_text="Whether this item has been purchased"
    )

    # Track which recipe this came from (if any)
    added_from_recipe = models.ForeignKey(
        'Recipe',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='shopping_list_items',
        help_text="Recipe this ingredient was added from"
    )

    notes = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text="Additional notes (e.g., 'organic', 'brand preference')"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for ShoppingListItem model."""
        ordering = ['is_purchased', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_purchased']),
            models.Index(fields=['user', '-created_at']),
        ]
        # Prevent duplicate items per user
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'ingredient_name'],
                name='unique_user_ingredient_name'
            )
        ]

    def __str__(self):
        """Return string representation of shopping list item."""
        status = "✓" if self.is_purchased else "○"
        quantity_str = f" ({self.quantity})" if self.quantity else ""
        return f"{status} {self.ingredient_name}{quantity_str}"

    def clean(self):
        """Validate and sanitize shopping list item data."""
        from django.core.exceptions import ValidationError

        # Strip and validate ingredient name
        if self.ingredient_name:
            self.ingredient_name = self.ingredient_name.strip()
            if not self.ingredient_name:
                raise ValidationError({
                    'ingredient_name': 'Ingredient name cannot be empty or only whitespace.'
                })

        # Strip quantity and notes
        if self.quantity:
            self.quantity = self.quantity.strip()

        if self.notes:
            self.notes = self.notes.strip()

        # If ingredient is linked, sync the name
        if self.ingredient:
            self.ingredient_name = str(self.ingredient.name)

    def save(self, *args, **kwargs):
        """Override save to run validation."""
        self.full_clean()
        super().save(*args, **kwargs)

    def mark_purchased(self):
        """Mark item as purchased."""
        self.is_purchased = True
        self.save()

    def mark_unpurchased(self):
        """Mark item as not purchased."""
        self.is_purchased = False
        self.save()

    def toggle_purchased(self):
        """Toggle purchased status."""
        self.is_purchased = not self.is_purchased
        self.save()

    def add_to_pantry(self):
        """
        Add this item to user's pantry if linked to an ingredient.

        Returns:
            bool: True if successfully added, False otherwise
        """
        if not self.ingredient:
            return False

        pantry, _ = Pantry.objects.get_or_create(user=self.user)
        pantry.ingredients.add(self.ingredient)
        return True

        
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
        """Meta options for ScanRateLimit model."""
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
