"""Service functions for USDA API integration."""
from services import usda_api


def search_usda_foods(query, allergen_objects, page_size=10):
    """
    Search USDA database and format results with allergen detection.

    Args:
        query: Search query string
        allergen_objects: QuerySet of Allergen objects
        page_size: Number of results to return

    Returns:
        List of formatted ingredient dictionaries
    """
    foods = usda_api.search_foods(query, page_size=page_size, use_cache=True)
    results = []

    for food in foods:
        name = food.get('description', '')
        brand = food.get('brandOwner', '') or 'Generic'

        calories = next(
            (nutrient.get("value", 0)
             for nutrient in food.get("foodNutrients", [])
             if nutrient.get("nutrientName") == "Energy"),
            0
        )

        detected_allergens = detect_allergens_from_name(name, allergen_objects)

        results.append({
            'name': name,
            'brand': brand,
            'calories': int(calories) if calories else 0,
            'fdc_id': food.get('fdcId', ''),
            'data_type': food.get('dataType', ''),
            'suggested_allergens': [
                {
                    'id': allergen.id,
                    'name': allergen.name,
                    'category': allergen.category
                }
                for allergen in detected_allergens
            ]
        })

    return results


def detect_allergens_from_name(ingredient_name, allergen_objects):
    """
    Detect potential allergens in an ingredient based on name matching.

    Args:
        ingredient_name: Name of the ingredient to check
        allergen_objects: QuerySet or list of Allergen objects

    Returns:
        List of Allergen objects that match
    """
    ingredient_lower = ingredient_name.lower()
    detected_allergens = []

    for allergen in allergen_objects:
        if allergen.name.lower() in ingredient_lower:
            if allergen not in detected_allergens:
                detected_allergens.append(allergen)
            continue

        for alt_name in allergen.alternative_names:
            if alt_name.lower() in ingredient_lower:
                if allergen not in detected_allergens:
                    detected_allergens.append(allergen)
                break

    return detected_allergens