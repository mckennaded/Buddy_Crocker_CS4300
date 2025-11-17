"""Service functions for recipe-related operations."""
from buddy_crocker.models import Recipe


def filter_recipes_by_allergens(recipes, exclude_allergen_ids):
    """
    Filter recipes by allergens.

    Args:
        recipes: QuerySet of recipes
        exclude_allergen_ids: List of allergen IDs to exclude

    Returns:
        Filtered QuerySet of recipes
    """
    recipes_with_allergens = Recipe.objects.filter(
        ingredients__allergens__id__in=exclude_allergen_ids
    ).distinct()

    return recipes.exclude(id__in=recipes_with_allergens)
