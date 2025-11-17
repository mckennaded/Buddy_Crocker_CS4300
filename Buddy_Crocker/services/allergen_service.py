"""Service functions for allergen-related operations."""


def get_user_allergens(user):
    """
    Extract user allergen information.

    Returns:
        tuple: (user_allergens, user_profile_allergen_ids)
    """
    user_allergens = []
    user_profile_allergen_ids = []

    if user.is_authenticated:
        try:
            profile = user.profile
            user_allergens = list(profile.allergens.all())
            user_profile_allergen_ids = [a.id for a in user_allergens]
        except Exception: # pylint: disable=broad-exception-caught
            pass

    return user_allergens, user_profile_allergen_ids


def get_allergen_context(all_allergens, user_allergens):
    """
    Determine allergen display context.

    Args:
        all_allergens: All allergens for the item
        user_allergens: User's allergen preferences

    Returns:
        dict: Context with allergen information
    """
    relevant_allergens = []
    has_allergen_conflict = False
    is_safe_for_user = False
    show_all_allergens = True

    if user_allergens:
        show_all_allergens = False
        relevant_allergens = [a for a in all_allergens if a in user_allergens]
        has_allergen_conflict = len(relevant_allergens) > 0
        is_safe_for_user = len(relevant_allergens) == 0
    elif user_allergens is not None:
        show_all_allergens = False
        is_safe_for_user = True

    return {
        'relevant_allergens': relevant_allergens,
        'has_allergen_conflict': has_allergen_conflict,
        'is_safe_for_user': is_safe_for_user,
        'show_all_allergens': show_all_allergens,
    }


def categorize_pantry_ingredients(pantry_ingredients, user_allergens):
    """
    Categorize pantry ingredients as safe or unsafe.

    Args:
        pantry_ingredients: QuerySet of ingredients
        user_allergens: List of user's allergens

    Returns:
        tuple: (safe_ingredients, unsafe_ingredients)
    """
    safe_ingredients = []
    unsafe_ingredients = []

    for ingredient in pantry_ingredients:
        ingredient_allergens = list(ingredient.allergens.all())
        relevant_allergens = [
            a for a in ingredient_allergens if a in user_allergens
        ]

        ingredient.relevant_allergens = relevant_allergens
        ingredient.has_conflict = len(relevant_allergens) > 0
        ingredient.is_safe = len(relevant_allergens) == 0

        if ingredient.has_conflict:
            unsafe_ingredients.append(ingredient)
        else:
            safe_ingredients.append(ingredient)

    return safe_ingredients, unsafe_ingredients
