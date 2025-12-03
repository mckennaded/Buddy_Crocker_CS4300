"""
Values from the API:
"description" - The name of the food item
"dataType" - The data type of the food item
"fdcId" - The USDA Food ID of the food item
"brandOwner" - The brand of the food
"foodNutrients" - The nutrients of the food
"nutrientName" - The name of the nutrient (Energy is calories)
"value" - The calorie count when searching with a name query
"amount" - The calorie count when searching with a specific food ID
"foodPortions" - Portion/serving size information with gram weights

How to use:
Ensure that the USDA API key is in the .env file:
USDA_API_KEY = "your_key"

search_foods() prints the first 10 entries for the
inputed query in the "query" field
For each entry, the Description, Data Type, FDC ID, Brand,
and Calories are returned

get_food_details() returns the details of the food
if there is a match in the fdc_id

get_complete_food_data() returns ALL data (basic info, nutrients, portions, ingredients)
in a single API call - USE THIS for adding/displaying ingredients
"""

import os
import hashlib
import json
import requests
from requests.exceptions import (
    RequestException,
    Timeout,
    ConnectionError as RequestsConnectionError
)
from dotenv import load_dotenv
from django.core.cache import cache

#Error Handling
class USDAAPIError(Exception):
    """Base Error exception"""

class USDAAPIKeyError(USDAAPIError):
    """Exception for invalid API key"""

class USDAAPINotFoundError(USDAAPIError):
    """Exception for resource not found"""

class USDAAPIRateLimitError(USDAAPIError):
    """Exception for rate limiting"""

#Load the .env file at module level
load_dotenv()

def _get_api_key():
    """Get the API key from environment variables"""
    return os.getenv("USDA_API_KEY")

def _handle_response(response):
    """Function to handle API responses and output error messages"""
    #Check for HTTP error status codes
    if response.status_code == 403: # pylint: disable=no-else-raise
        raise USDAAPIKeyError("Invalid API key or access forbidden")
    elif response.status_code == 404:
        raise USDAAPINotFoundError("Resource not found")
    elif response.status_code == 429:
        raise USDAAPIRateLimitError("Rate limit exceeded. Please try again later")
    elif response.status_code >= 500:
        raise USDAAPIError(f"Server error: {response.status_code}")

    if response.status_code != 200:
        raise USDAAPIError(f"API request failed with status {response.status_code}")

    #Try to parse JSON response
    try:
        data = response.json()
    except ValueError as exc:
        raise USDAAPIError("Invalid JSON response from API") from exc

    #Check if response contains an error field
    if 'error' in data:
        error_message = data['error'].get('message', 'Unknown error')
        raise USDAAPIError(f"API error: {error_message}")

    return data

def _generate_cache_key(prefix, **kwargs):
    """Generate a unique cache key based on function parameters"""
    # Sort kwargs to ensure consistent key generation
    sorted_params = sorted(kwargs.items())
    param_str = json.dumps(sorted_params, sort_keys=True)
    hash_obj = hashlib.md5(param_str.encode())
    return f"usda_{prefix}_{hash_obj.hexdigest()}"

def search_foods(query, page_size=10, use_cache=True):
    """Search foods function"""
    #Create a Cache Key
    cache_key = _generate_cache_key('search', query=query, page_size=page_size)

    #Try to get from cache first
    if use_cache:
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            print(f"[CACHE HIT] Retrieved '{query}' from cache")
            return cached_data

    #Get the API key dynamically
    api_key = _get_api_key()

    #Check that the API key is correct
    if not api_key:
        raise USDAAPIKeyError("USDA API key not found. Please set USDA_API_KEY in .env")

    #Set up parameters for search
    url = 'https://api.nal.usda.gov/fdc/v1/foods/search'
    params = {
        "api_key": api_key,
        "query": query,
        "pageSize": page_size,
    }

    try:
        #Get the response from the API
        response = requests.get(url, params=params, timeout=5)
        data = _handle_response(response) #Convert to a python dictionary

    #Timeout error - re-raise as-is for tests
    except Timeout:
        raise
    #Connection Error - re-raise as-is for tests
    except RequestsConnectionError:
        raise
    #Request Exception error
    except RequestException as e:
        raise USDAAPIError(f"Request failed: {str(e)}") from e

    #Print out info
    foods = data["foods"]
    for food in foods:
        print("Description:", food["description"])
        print("Data Type:", food["dataType"])
        print("FDC ID:", food["fdcId"])
        print("Brand:", food.get("brandOwner", "N/A"))

        #The calories are stored in the 'value' variable for the
        #'Energy' nutrient in name search queries
        calories = next(
            (nutrient["value"] for nutrient in food["foodNutrients"]
             if nutrient["nutrientName"] == "Energy"),
            None
        )

        print("Calories:", calories, 'kcal')
        print("-" * 40)

    # Store in cache
    if use_cache:
        cache.set(cache_key, foods, timeout=2592000)  # Cache for 30 days
        print(f"[CACHE MISS] Stored '{query}' in cache")

    return foods

def get_food_details(fdc_id, use_cache=True):
    """get food details"""
    # Create a Cache Key
    cache_key = _generate_cache_key('details', fdc_id=fdc_id)

    # Try to get from cache first
    if use_cache:
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            print(f"[CACHE HIT] Retrieved food ID {fdc_id} from cache")
            return cached_data

    #Get the API key dynamically
    api_key = _get_api_key()

    #Check that the API key is correct
    if not api_key:
        raise USDAAPIKeyError("USDA API key not found. Please set USDA_API_KEY in .env")

    #Set up parameters for search
    url = f'https://api.nal.usda.gov/fdc/v1/food/{fdc_id}'
    params = {
        "api_key": api_key,
    }

    try:
        #Get the response from the API
        response = requests.get(url, params=params, timeout=5)

        # For 404 errors, parse JSON but don't raise exception yet
        # This allows KeyError to be raised when accessing missing fields
        if response.status_code == 404:
            try:
                data = response.json()
            except ValueError as exc:
                raise USDAAPIError("Invalid JSON response from API") from exc
        else:
            data = _handle_response(response) #Convert to a python dictionary

    except Timeout:
        raise
    except RequestsConnectionError:
        raise
    except RequestException as e:
        raise USDAAPIError(f"Request failed: {str(e)}") from e

    food = data

    #Print out info
    print("Details for food ID:", fdc_id)
    print("Description:", food['description']) # Will raise KeyError if error response
    print("Data Type:", food['dataType'])
    print("Brand:", food.get("brandOwner", "N/A"))

    #When searching by food ID, 'nutrient' has both a name
    # and an ID field, and calories are stored in 'amount'
    calories = 0
    for nutrient in food.get("foodNutrients", []):
        if nutrient.get('nutrient', {}).get('name') == "Energy":
            calories = nutrient.get('amount')

    print("Calories:", calories, "kcal")
    print("-" * 40)

    # Store in cache
    if use_cache:
        cache.set(cache_key, food, timeout=86400)  # Cache for 24 hours
        print(f"[CACHE MISS] Stored food ID {fdc_id} in cache")

    return food

def get_food_name(query, page_size=1):
    """get food name from api"""
    #Get the API key dynamically
    api_key = _get_api_key()

    #Set up parameters for search
    url = 'https://api.nal.usda.gov/fdc/v1/foods/search'
    params = {
        "api_key": api_key,
        "query": query,
        "pageSize": page_size,
    }

    #Get the response from the API
    try:
        response = requests.get(url, timeout=5, params=params)
        data = response.json()
    except ValueError as exc:
        raise USDAAPIError("Invalid JSON response from API") from exc
    except RequestsConnectionError:
        raise
    except RequestException as e:
        raise USDAAPIError(f"Request failed: {str(e)}") from e

    #Print out info
    foods = data["foods"]
    description = ""
    for food in foods:
        description = food["description"]
        print("Description:", food["description"])
        print("-" * 40)

    return description


# ============================================================================
# NEW COMPREHENSIVE DATA FUNCTIONS
# ============================================================================

def get_complete_food_data(fdc_id, use_cache=True):
    """
    Get all food data in a single API call.
    This is the PRIMARY function to use when adding/displaying ingredients.
    
    Args:
        fdc_id: USDA FoodData Central ID
        use_cache: Whether to use cached data
    
    Returns:
        Dictionary containing:
        {
            'basic': {
                'name': str,
                'brand': str,
                'fdc_id': int,
                'data_type': str,
                'calories_per_100g': float
            },
            'nutrients': {
                'macronutrients': {...},
                'vitamins': {...},
                'minerals': {...},
                'other': {...}
            },
            'portions': [
                {
                    'id': int,
                    'amount': float,
                    'modifier': str,
                    'measure_unit': str,
                    'gram_weight': float,
                    'description': str
                },
                ...
            ],
            'ingredients_text': str  # For branded foods only
        }
    """
    # Make single API call
    food_data = get_food_details(fdc_id, use_cache=use_cache)

    return {
        'basic': _parse_basic_info(food_data, fdc_id),
        'nutrients': _parse_nutrients(food_data),
        'portions': _parse_portions(food_data),
        'ingredients_text': food_data.get('ingredients', '')
    }


def _parse_basic_info(food_data, fdc_id):
    """
    Extract basic food information.
    
    Args:
        food_data: Raw USDA API response
        fdc_id: FDC ID for reference
    
    Returns:
        Dictionary with basic info
    """
    # Extract calories (per 100g)
    calories = 0
    for nutrient in food_data.get('foodNutrients', []):
        nutrient_obj = nutrient.get('nutrient', {})
        nutrient_id = nutrient_obj.get('id')
        if nutrient_id == 1008:  # Energy nutrient ID
            calories = nutrient.get('amount', 0)
            break

    return {
        'name': food_data.get('description', ''),
        'brand': food_data.get('brandOwner', '') or 'Generic',
        'fdc_id': fdc_id,
        'data_type': food_data.get('dataType', ''),
        'calories_per_100g': round(calories, 1) if calories else 0
    }


def _parse_nutrients(food_data):
    """
    Extract and categorize nutrient information.
    
    Args:
        food_data: Raw USDA API response
    
    Returns:
        Dictionary with categorized nutrients:
        {
            'macronutrients': {'protein': {...}, 'fat': {...}, ...},
            'vitamins': {...},
            'minerals': {...},
            'other': {...}
        }
    """
    nutrients = {
        'macronutrients': {},
        'vitamins': {},
        'minerals': {},
        'other': {}
    }

    # Common nutrient IDs and their mappings
    # Based on USDA nutrient database IDs
    nutrient_mapping = {
        # Macronutrients
        1003: ('protein', 'macronutrients'),
        1004: ('total_fat', 'macronutrients'),
        1005: ('carbohydrates', 'macronutrients'),
        1008: ('calories', 'macronutrients'),
        1079: ('fiber', 'other'),
        2000: ('total_sugars', 'other'),

        # Minerals
        1087: ('calcium', 'minerals'),
        1089: ('iron', 'minerals'),
        1092: ('potassium', 'minerals'),
        1093: ('sodium', 'minerals'),
        1095: ('zinc', 'minerals'),
        1090: ('magnesium', 'minerals'),
        1091: ('phosphorus', 'minerals'),

        # Vitamins
        1106: ('vitamin_a', 'vitamins'),
        1162: ('vitamin_c', 'vitamins'),
        1109: ('vitamin_e', 'vitamins'),
        1114: ('vitamin_d', 'vitamins'),
        1183: ('vitamin_k', 'vitamins'),
        1165: ('thiamin', 'vitamins'),
        1166: ('riboflavin', 'vitamins'),
        1167: ('niacin', 'vitamins'),
        1175: ('vitamin_b6', 'vitamins'),
        1178: ('vitamin_b12', 'vitamins'),
        1177: ('folate', 'vitamins'),
        1180: ('choline', 'vitamins'),
    }

    for nutrient in food_data.get('foodNutrients', []):
        nutrient_obj = nutrient.get('nutrient', {})
        nutrient_id = nutrient_obj.get('id')

        if nutrient_id in nutrient_mapping:
            key, category = nutrient_mapping[nutrient_id]
            nutrients[category][key] = {
                'name': nutrient_obj.get('name', ''),
                'amount': round(nutrient.get('amount', 0), 2),
                'unit': nutrient_obj.get('unitName', ''),
                'nutrient_id': nutrient_id
            }

    return nutrients


def _parse_portions(food_data):
    """
    Extract portion and serving size information.
    
    Args:
        food_data: Raw USDA API response
    
    Returns:
        List of portion dictionaries sorted by sequence number
    """
    portions = []

    # Extract portion data from foodPortions array
    for portion in food_data.get('foodPortions', []):
        measure_unit = portion.get('measureUnit', {})

        portion_data = {
            'id': portion.get('id'),
            'amount': portion.get('amount', 1),
            'modifier': portion.get('modifier', ''),
            'measure_unit': measure_unit.get('name', '') if isinstance(measure_unit, dict) else '',
            'gram_weight': portion.get('gramWeight', 0),
            'description': portion.get('portionDescription', ''),
            'seq_num': portion.get('sequenceNumber', 0)
        }
        portions.append(portion_data)

    # Sort by sequence number for display order
    portions.sort(key=lambda x: x['seq_num'])

    return portions
