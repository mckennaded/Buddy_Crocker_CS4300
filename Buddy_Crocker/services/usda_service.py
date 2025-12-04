""" Service functions for USDA API integration.

This module provides high-level service functions for working with USDA data,
including allergen detection and data formatting.
"""

import logging
from buddy_crocker.models import Allergen
from services import usda_api

logger = logging.getLogger(__name__)


def search_usda_foods(query, allergen_objects, page_size=10):
    """
    Search USDA database and format results with allergen detection.
    
    Args:
        query: Search query string
        allergen_objects: QuerySet of Allergen objects
        page_size: Number of results to return
    
    Returns:
        List of formatted ingredient dictionaries
        
    Raises:
        usda_api.USDAAPIKeyError: Invalid API key
        usda_api.USDAAPIRateLimitError: Rate limit exceeded
        usda_api.USDAAPIError: Other API errors
    """
    # Let exceptions propagate to caller
    foods = usda_api.search_foods(query, page_size=page_size, use_cache=True)
    results = []

    for food in foods: # pylint: disable=too-many-nested-blocks
        if not isinstance(food, dict):
            logger.warning("Invalid food item format in search results")
            continue

        name = food.get('description', '')
        brand = food.get('brandOwner', '') or 'Generic'

        # Extract calories safely
        calories = 0
        food_nutrients = food.get('foodNutrients', [])
        if isinstance(food_nutrients, list):
            for nutrient in food_nutrients:
                if isinstance(nutrient, dict):
                    if nutrient.get('nutrientName') == 'Energy':
                        try:
                            calories = int(nutrient.get('value', 0))
                        except (ValueError, TypeError):
                            calories = 0
                        break

        detected_allergens = detect_allergens_from_name(name, allergen_objects)

        results.append({
            'name': name,
            'brand': brand,
            'calories': calories,
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
    if not ingredient_name or not isinstance(ingredient_name, str):
        return []

    ingredient_lower = ingredient_name.lower()
    detected_allergens = []

    for allergen in allergen_objects:
        # Check main allergen name
        if allergen.name.lower() in ingredient_lower:
            if allergen not in detected_allergens:
                detected_allergens.append(allergen)
            continue

        # Check alternative names
        alternative_names = allergen.alternative_names
        if not isinstance(alternative_names, list):
            continue

        for alt_name in alternative_names:
            if isinstance(alt_name, str) and alt_name.lower() in ingredient_lower:
                if allergen not in detected_allergens:
                    detected_allergens.append(allergen)
                break

    return detected_allergens


def get_complete_ingredient_data(fdc_id, allergen_objects=None):
    """
    Get complete ingredient data including nutrients, portions, and allergens.
    
    This is the PRIMARY service function to use when adding/displaying ingredients.
    
    Args:
        fdc_id: USDA FoodData Central ID
        allergen_objects: Optional QuerySet of Allergen objects for detection
    
    Returns:
        Dictionary containing all ingredient data with detected allergens
        
    Raises:
        usda_api.USDAAPIKeyError: Invalid API key
        usda_api.USDAAPINotFoundError: Food not found
        usda_api.USDAAPIRateLimitError: Rate limit exceeded
        usda_api.USDAAPIError: Other API errors
    """
    # Let API exceptions propagate to caller
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


def format_nutrient_display(nutrients):
    """
    Format nutrient data for template display.
    
    Args:
        nutrients: Dictionary of categorized nutrients from get_complete_ingredient_data
    
    Returns:
        Dictionary with formatted strings for display
    """
    if not isinstance(nutrients, dict):
        logger.warning("Invalid nutrients format in format_nutrient_display")
        return {
            'macronutrients': [],
            'vitamins': [],
            'minerals': [],
            'other': []
        }

    display = {
        'macronutrients': [],
        'vitamins': [],
        'minerals': [],
        'other': []
    }

    for category, nutrient_dict in nutrients.items():
        if category not in display:
            continue

        if not isinstance(nutrient_dict, dict):
            logger.warning(
                "Invalid nutrient_dict format for category %s",
                category
            )
            continue

        for _key, nutrient in nutrient_dict.items():
            if not isinstance(nutrient, dict):
                continue

            try:
                amount = float(nutrient.get('amount', 0))
                unit = nutrient.get('unit', '')
                name = nutrient.get('name', '')

                display[category].append({
                    'label': name,
                    'value': amount,
                    'unit': unit,
                    'formatted': f"{amount:.1f} {unit}"
                })
            except (ValueError, TypeError) as e:
                logger.debug(
                    "Error formatting nutrient %s: %s",
                    nutrient.get('name'),
                    str(e)
                )
                continue

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
    try:
        calories = float(calories_per_100g)
        weight = float(gram_weight)
    except (ValueError, TypeError):
        return 0

    if not calories or not weight:
        return 0

    return round((calories * weight) / 100, 1)


def calculate_nutrient_for_portion(nutrient_per_100g, gram_weight):
    """
    Calculate any nutrient amount for a specific portion size.
    
    Args:
        nutrient_per_100g: Nutrient value per 100 grams
        gram_weight: Weight of the portion in grams
    
    Returns:
        Calculated nutrient amount for the portion (rounded to 2 decimals)
    """
    try:
        nutrient = float(nutrient_per_100g)
        weight = float(gram_weight)
    except (ValueError, TypeError):
        return 0

    if not nutrient or not weight:
        return 0

    return round((nutrient * weight) / 100, 2)

def fetch_usda_data_with_error_handling(request, fdc_id, ingredient_name):
    """
    Fetch USDA data and return result with error information.
    
    Returns:
        tuple: (complete_data, should_continue)
        - complete_data: The fetched data or None
        - should_continue: False if we should abort ingredient creation
        - error_info: Dict with 'level' and 'message' for user feedback
    """
    try:
        logger.info("Fetching USDA data for fdc_id: %s", fdc_id)
        complete_data = get_complete_ingredient_data(
            fdc_id,
            Allergen.objects.all()
        )

        logger.info("Successfully fetched nutrition data")
        return complete_data, False, None

    except usda_api.USDAAPIKeyError:
        logger.critical("Invalid USDA API key")
        return None, True, {
            'level': 'error',
            'message': 'Configuration error. Please contact support.'
        }

    except usda_api.USDAAPIRateLimitError:
        logger.warning(
            "USDA API rate limit hit for user %s",
            request.user.username
        )
        return None, False, {
            'level': 'warning',
            'message': (
                f"Added {ingredient_name} but couldn't fetch nutrition data. "
                "Too many requests - please try again in a moment."
            )
        }

    except usda_api.USDAAPINotFoundError:
        logger.warning(
            "USDA food not found for fdc_id %s",
            fdc_id
        )
        return None, False, {
            'level': 'warning',
            'message': (
                f"Added {ingredient_name} but the selected food was not "
                "found in the USDA database."
            )
        }

    except usda_api.USDAAPIError as e:
        logger.error(
            "USDA API error for fdc_id %s: %s",
            fdc_id,
            str(e)
        )
        return None, False, {
            'level': 'warning',
            'message': (
                f"Added {ingredient_name} but couldn't fetch complete nutrition "
                "data. Service temporarily unavailable."
            )
        }

    except Exception as e: # pylint: disable=broad-exception-caught
        logger.exception(
            "Unexpected error fetching USDA data for fdc_id %s: %s",
            fdc_id,
            str(e)
        )
        return None, False, {
            'level': 'warning',
            'message': (
                f"Added {ingredient_name} but couldn't fetch nutrition data. "
                "An unexpected error occurred."
            )
        }
