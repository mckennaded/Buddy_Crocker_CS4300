"""
USDA FoodData Central API Client

This module provides a robust client for interacting with the USDA API.
Includes retry logic, comprehensive error handling, and data validation.
"""

import os
import hashlib
import json
import logging
import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import (
    RequestException,
    Timeout,
    ConnectionError as RequestsConnectionError
)
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from django.core.cache import cache

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


# ============================================================================
# Custom Exceptions
# ============================================================================

class USDAAPIError(Exception):
    """Base exception for USDA API errors."""


class USDAAPIKeyError(USDAAPIError):
    """Exception for invalid API key."""


class USDAAPINotFoundError(USDAAPIError):
    """Exception for resource not found (404)."""


class USDAAPIRateLimitError(USDAAPIError):
    """Exception for rate limiting (429)."""


class USDAAPIValidationError(USDAAPIError):
    """Exception for invalid response data."""


# ============================================================================
# Session Management with Retry Logic
# ============================================================================

def _create_session_with_retries():
    """
    Create requests session with automatic retry logic.
    
    Retries on:
    - 429 (Rate Limit)
    - 500, 502, 503, 504 (Server Errors)
    
    Returns:
        requests.Session: Configured session with retry adapter
    """
    session = requests.Session()

    retry_strategy = Retry(
        total=3,
        backoff_factor=1,  # Wait 1, 2, 4 seconds between retries
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False  # We'll handle status codes ourselves
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


# Global session instance
_session = _create_session_with_retries()


# ============================================================================
# Helper Functions
# ============================================================================

def _get_api_key():
    """
    Get the USDA API key from environment variables.
    
    Returns:
        str: API key
        
    Raises:
        USDAAPIKeyError: If API key is not configured
    """
    api_key = os.getenv("USDA_API_KEY")
    if not api_key:
        raise USDAAPIKeyError(
            "USDA API key not found. Please set USDA_API_KEY in .env"
        )
    return api_key


def _handle_response(response):
    """
    Handle API response and raise appropriate exceptions.
    
    Args:
        response: requests.Response object
        
    Returns:
        dict: Parsed JSON response
        
    Raises:
        USDAAPIKeyError: For 403 errors
        USDAAPINotFoundError: For 404 errors
        USDAAPIRateLimitError: For 429 errors
        USDAAPIError: For other errors
    """
    # Check for HTTP error status codes
    if response.status_code == 403:
        raise USDAAPIKeyError("Invalid API key or access forbidden")
    if response.status_code == 404:
        raise USDAAPINotFoundError("Resource not found")
    if response.status_code == 429:
        raise USDAAPIRateLimitError(
            "Rate limit exceeded. Please try again later"
        )
    if response.status_code >= 500:
        raise USDAAPIError(f"Server error: {response.status_code}")
    if response.status_code != 200:
        raise USDAAPIError(
            f"API request failed with status {response.status_code}"
        )

    # Try to parse JSON response
    try:
        data = response.json()
    except ValueError as exc:
        raise USDAAPIValidationError(
            "Invalid JSON response from API"
        ) from exc

    # Check if response contains an error field
    if 'error' in data:
        # Handle both string and dict error formats
        error = data['error']
        if isinstance(error, dict):
            error_message = error.get('message', 'Unknown error')
        elif isinstance(error, str):
            error_message = error
        else:
            error_message = 'Unknown error'
        raise USDAAPIError(f"API error: {error_message}")

    return data


def _generate_cache_key(prefix, **kwargs):
    """
    Generate a unique cache key based on function parameters.
    
    Args:
        prefix: String prefix for the cache key
        **kwargs: Parameters to include in cache key
        
    Returns:
        str: Unique cache key
    """
    sorted_params = sorted(kwargs.items())
    param_str = json.dumps(sorted_params, sort_keys=True)
    hash_obj = hashlib.md5(param_str.encode())
    return f"usda_{prefix}_{hash_obj.hexdigest()}"


def _validate_foods_response(data):
    """
    Validate that foods response has expected structure.
    
    Args:
        data: Response data dictionary
        
    Returns:
        list: List of food items
        
    Raises:
        USDAAPIValidationError: If structure is invalid
    """
    if 'foods' not in data:
        raise USDAAPIValidationError("Response missing 'foods' field")

    foods = data['foods']
    if not isinstance(foods, list):
        raise USDAAPIValidationError(
            f"'foods' should be list, got {type(foods)}"
        )

    return foods


def _validate_food_detail_response(data):
    """
    Validate that food detail response has expected structure.
    
    Args:
        data: Response data dictionary
        
    Raises:
        USDAAPIValidationError: If required fields are missing
    """
    required_fields = ['description', 'fdcId', 'dataType']
    missing_fields = [field for field in required_fields if field not in data]

    if missing_fields:
        raise USDAAPIValidationError(
            f"Response missing required fields: {', '.join(missing_fields)}"
        )


# ============================================================================
# Public API Functions
# ============================================================================

def search_foods(query, page_size=10, use_cache=True):
    """
    Search for foods in USDA database.
    
    Args:
        query: Search query string
        page_size: Number of results to return (default: 10)
        use_cache: Whether to use cached results (default: True)
        
    Returns:
        list: List of food dictionaries
        
    Raises:
        USDAAPIKeyError: Invalid API key
        USDAAPIRateLimitError: Rate limit exceeded
        USDAAPIError: Other API errors
    """
    # Generate cache key
    cache_key = _generate_cache_key('search', query=query, page_size=page_size)

    # Try to get from cache first
    if use_cache:
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            logger.debug("Cache hit for query: %s", query)
            return cached_data

    # Get API key
    api_key = _get_api_key()

    # Set up parameters for search
    url = 'https://api.nal.usda.gov/fdc/v1/foods/search'
    params = {
        "api_key": api_key,
        "query": query,
        "pageSize": page_size,
    }

    try:
        # Make API request with retry logic
        logger.debug("Searching USDA API for: %s", query)
        response = _session.get(url, params=params, timeout=5)
        data = _handle_response(response)

        # Validate response structure
        foods = _validate_foods_response(data)

        logger.info("Found %d results for query: %s", len(foods), query)

    except Timeout as exc:
        logger.error("USDA API timeout for query: %s", query)
        raise USDAAPIError("Request timeout (>5s)") from exc
    except RequestsConnectionError as exc:
        logger.error("USDA API connection error for query: %s", query)
        raise USDAAPIError("Connection failed") from exc
    except (USDAAPIKeyError, USDAAPIRateLimitError, USDAAPIValidationError):
        # Re-raise our custom exceptions
        raise # pylint: disable=try-except-raise
    except RequestException as exc:
        logger.error("USDA API request failed for query %s: %s", query, str(exc))
        raise USDAAPIError(f"Request failed: {str(exc)}") from exc

    # Store in cache (30 days for search results)
    if use_cache:
        cache.set(cache_key, foods, timeout=2592000)
        logger.debug("Cache miss - stored query: %s", query)

    return foods


def get_food_details(fdc_id, use_cache=True):
    """
    Get detailed information for a specific food by FDC ID.
    
    Args:
        fdc_id: USDA Food Data Central ID
        use_cache: Whether to use cached results (default: True)
        
    Returns:
        dict: Food details dictionary
        
    Raises:
        USDAAPIKeyError: Invalid API key
        USDAAPINotFoundError: Food not found
        USDAAPIRateLimitError: Rate limit exceeded
        USDAAPIError: Other API errors
    """
    # Generate cache key
    cache_key = _generate_cache_key('details', fdc_id=fdc_id)

    # Try to get from cache first
    if use_cache:
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            logger.debug("Cache hit for FDC ID: %s", fdc_id)
            return cached_data

    # Get API key
    api_key = _get_api_key()

    # Set up URL and parameters
    url = f'https://api.nal.usda.gov/fdc/v1/food/{fdc_id}'
    params = {"api_key": api_key}

    try:
        # Make API request with retry logic
        logger.debug("Fetching food details for FDC ID: %s", fdc_id)
        response = _session.get(url, params=params, timeout=5)
        data = _handle_response(response)

        # Validate response structure
        _validate_food_detail_response(data)

        logger.info("Retrieved details for FDC ID: %s", fdc_id)

    except Timeout as exc:
        logger.error("USDA API timeout for FDC ID: %s", fdc_id)
        raise USDAAPIError("Request timeout (>5s)") from exc
    except RequestsConnectionError as exc:
        logger.error("USDA API connection error for FDC ID: %s", fdc_id)
        raise USDAAPIError("Connection failed") from exc
    except (USDAAPIKeyError, USDAAPINotFoundError,
            USDAAPIRateLimitError, USDAAPIValidationError):
        # Re-raise our custom exceptions
        raise # pylint: disable=try-except-raise
    except RequestException as exc:
        logger.error(
            "USDA API request failed for FDC ID %s: %s",
            fdc_id,
            str(exc)
        )
        raise USDAAPIError(f"Request failed: {str(exc)}") from exc

    # Store in cache (24 hours for details)
    if use_cache:
        cache.set(cache_key, data, timeout=86400)
        logger.debug("Cache miss - stored FDC ID: %s", fdc_id)

    return data


# ============================================================================
# Comprehensive Data Functions
# ============================================================================

def get_complete_food_data(fdc_id, use_cache=True):
    """
    Get all food data in a single API call.
    
    This is the PRIMARY function to use when adding/displaying ingredients.
    
    Args:
        fdc_id: USDA FoodData Central ID
        use_cache: Whether to use cached data (default: True)
    
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
            'portions': [...],
            'ingredients_text': str
        }
        
    Raises:
        USDAAPIKeyError: Invalid API key
        USDAAPINotFoundError: Food not found
        USDAAPIRateLimitError: Rate limit exceeded
        USDAAPIError: Other API errors
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
    Extract basic food information with validation.
    
    Args:
        food_data: Raw USDA API response
        fdc_id: FDC ID for reference
    
    Returns:
        Dictionary with basic info
    """
    if not isinstance(food_data, dict):
        logger.warning("Invalid food_data type for FDC ID %s", fdc_id)
        food_data = {}

    # Extract calories (per 100g)
    calories = 0
    food_nutrients = food_data.get('foodNutrients', [])

    if not isinstance(food_nutrients, list):
        logger.warning(
            "foodNutrients is not a list for FDC ID %s",
            fdc_id
        )
        food_nutrients = []

    for nutrient in food_nutrients:
        if not isinstance(nutrient, dict):
            continue

        nutrient_obj = nutrient.get('nutrient', {})
        if not isinstance(nutrient_obj, dict):
            continue

        nutrient_id = nutrient_obj.get('id')
        if nutrient_id == 1008:  # Energy nutrient ID
            amount = nutrient.get('amount', 0)
            try:
                calories = float(amount) if amount else 0
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid calorie value for FDC ID %s: %s",
                    fdc_id,
                    amount
                )
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
    Extract and categorize nutrient information with validation.
    
    Args:
        food_data: Raw USDA API response
    
    Returns:
        Dictionary with categorized nutrients
    """
    nutrients = {
        'macronutrients': {},
        'vitamins': {},
        'minerals': {},
        'other': {}
    }

    # Nutrient ID mappings
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

    food_nutrients = food_data.get('foodNutrients', [])
    if not isinstance(food_nutrients, list):
        logger.warning("foodNutrients is not a list in _parse_nutrients")
        return nutrients

    for nutrient in food_nutrients:
        if not isinstance(nutrient, dict):
            continue

        nutrient_obj = nutrient.get('nutrient', {})
        if not isinstance(nutrient_obj, dict):
            continue

        nutrient_id = nutrient_obj.get('id')

        # Skip if no valid nutrient ID
        if not nutrient_id or nutrient_id not in nutrient_mapping:
            continue

        key, category = nutrient_mapping[nutrient_id]

        # Validate required fields exist before processing
        if not nutrient_obj.get('name') or not nutrient_obj.get('unitName'):
            logger.debug(
                "Skipping nutrient %s: missing required fields (name or unit)",
                nutrient_id
            )
            continue

        # Validate amount is present and convertible
        amount_value = nutrient.get('amount')
        if amount_value is None:
            logger.debug("Skipping nutrient %s: missing amount", nutrient_id)
            continue

        try:
            amount = float(amount_value)
        except (ValueError, TypeError):
            logger.debug(
                "Skipping nutrient %s: invalid amount %s",
                nutrient_id,
                amount_value
            )
            continue

        nutrients[category][key] = {
            'name': nutrient_obj.get('name', ''),
            'amount': round(amount, 2),
            'unit': nutrient_obj.get('unitName', ''),
            'nutrient_id': nutrient_id
        }

    return nutrients


def _parse_portions(food_data):
    """
    Extract portion and serving size information with validation.
    
    Args:
        food_data: Raw USDA API response
    
    Returns:
        List of portion dictionaries sorted by sequence number
    """
    portions = []

    food_portions = food_data.get('foodPortions', [])
    if not isinstance(food_portions, list):
        logger.warning("foodPortions is not a list in _parse_portions")
        return portions

    for portion in food_portions:
        if not isinstance(portion, dict):
            continue

        measure_unit = portion.get('measureUnit', {})

        # Handle both dict and string measure_unit
        if isinstance(measure_unit, dict):
            unit_name = measure_unit.get('name', '')
        elif isinstance(measure_unit, str):
            unit_name = measure_unit
        else:
            unit_name = ''

        try:
            gram_weight = float(portion.get('gramWeight', 0))
            amount = float(portion.get('amount', 1))
            seq_num = int(portion.get('sequenceNumber', 0))
        except (ValueError, TypeError):
            logger.debug("Invalid portion data: %s", portion)
            continue

        portion_data = {
            'id': portion.get('id'),
            'amount': amount,
            'modifier': portion.get('modifier', ''),
            'measure_unit': unit_name,
            'gram_weight': gram_weight,
            'description': portion.get('portionDescription', ''),
            'seq_num': seq_num
        }
        portions.append(portion_data)

    # Sort by sequence number for display order
    portions.sort(key=lambda x: x['seq_num'])

    return portions
