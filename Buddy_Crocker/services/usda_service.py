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


# ============================================================================
# NEW COMPREHENSIVE DATA FUNCTIONS
# ============================================================================

def get_complete_ingredient_data(fdc_id, allergen_objects=None):
    """
    Get complete ingredient data including nutrients, portions, and allergens.
    This is the PRIMARY service function to use when adding/displaying ingredients.
    
    Args:
        fdc_id: USDA FoodData Central ID
        allergen_objects: Optional QuerySet of Allergen objects for detection
    
    Returns:
        Dictionary containing all ingredient data:
        {
            'basic': {...},
            'nutrients': {...},
            'portions': [...],
            'detected_allergens': [...]  # Added by this function
        }
    """
    try:
        # Single API call gets everything
        data = usda_api.get_complete_food_data(fdc_id, use_cache=True)

        # Enhance with allergen detection from name AND ingredients text
        if allergen_objects:
            search_text = f"{data['basic']['name']} {data['ingredients_text']}"
            detected = detect_allergens_from_name(search_text, allergen_objects)
            data['detected_allergens'] = [
                {
                    'id': allergen.id,
                    'name': allergen.name,
                    'category': allergen.category
                }
                for allergen in detected
            ]
        else:
            data['detected_allergens'] = []

        return data

    except usda_api.USDAAPIError as e:
        print(f"Error fetching complete data for FDC ID {fdc_id}: {e}")
        # Return empty structure on error
        return {
            'basic': {
                'name': '',
                'brand': 'Generic',
                'fdc_id': fdc_id,
                'data_type': '',
                'calories_per_100g': 0
            },
            'nutrients': {
                'macronutrients': {},
                'vitamins': {},
                'minerals': {},
                'other': {}
            },
            'portions': [],
            'ingredients_text': '',
            'detected_allergens': []
        }


def format_nutrient_display(nutrients):
    """
    Format nutrient data for template display.
    
    Args:
        nutrients: Dictionary of categorized nutrients from get_complete_ingredient_data
    
    Returns:
        Dictionary with formatted strings for display
    """
    display = {
        'macronutrients': [],
        'vitamins': [],
        'minerals': [],
        'other': []
    }

    for category, nutrient_dict in nutrients.items():
        for key, nutrient in nutrient_dict.items():
            display[category].append({
                'label': nutrient['name'],
                'value': nutrient['amount'],
                'unit': nutrient['unit'],
                'formatted': f"{nutrient['amount']:.1f} {nutrient['unit']}"
            })

    return display


def calculate_portion_calories(calories_per_100g, gram_weight):
    """
    Calculate calories for a specific portion size.
    
    Args:
        calories_per_100g: Calorie value per 100 grams
        gram_weight: Weight of the portion in grams
    
    Returns:
        Calculated calories for the portion (rounded to 1 decimal)
    """
    if not calories_per_100g or not gram_weight:
        return 0

    return round((calories_per_100g * gram_weight) / 100, 1)


def calculate_nutrient_for_portion(nutrient_per_100g, gram_weight):
    """
    Calculate any nutrient amount for a specific portion size.
    
    Args:
        nutrient_per_100g: Nutrient value per 100 grams
        gram_weight: Weight of the portion in grams
    
    Returns:
        Calculated nutrient amount for the portion (rounded to 2 decimals)
    """
    if not nutrient_per_100g or not gram_weight:
        return 0

    return round((nutrient_per_100g * gram_weight) / 100, 2)
