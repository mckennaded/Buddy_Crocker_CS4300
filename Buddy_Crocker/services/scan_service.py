"""
Service functions for pantry scanning with GPT-4 Vision.

Includes improved error handling and USDA integration.
"""
import os
import json
import base64
import logging
from typing import List, Dict
from openai import OpenAI
from django.utils import timezone

from buddy_crocker.models import ScanRateLimit, Ingredient, Allergen, Pantry
from services.ingredient_validator import USDAIngredientValidator
from services.usda_service import get_complete_ingredient_data
from services import usda_api

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Extract client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# pylint: disable-next=too-many-locals
def process_pantry_scan(request):  # pylint: disable=too-many-return-statements
    """
    Process pantry image scan request.

    Args:
        request: Django request object

    Returns:
        dict: Response data with ingredients or error
    """
    # Check rate limit
    is_allowed, scans_remaining, reset_time = ScanRateLimit.check_rate_limit(
        request.user,
        max_scans=5,
        time_window_minutes=5
    )

    if not is_allowed:
        logger.warning("Rate limit exceeded for user: %s", request.user.username)
        reset_minutes = (reset_time - timezone.now()).seconds // 60
        return {
            'success': False,
            'error': 'rate_limit_exceeded',
            'message': (
                'You have reached the maximum of 5 scans per 5 minutes. '
                f'Please try again in {reset_minutes} minute(s).'
            ),
            'scans_remaining': 0,
            'reset_time': reset_time.isoformat() if reset_time else None,
            'status_code': 429
        }

    # Validate image file
    if 'image' not in request.FILES:
        logger.error("No image file provided")
        return {
            'success': False,
            'error': 'no_image',
            'message': 'No image file provided.',
            'status_code': 400
        }

    image_file = request.FILES['image']
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/jpg']
    if image_file.content_type not in allowed_types:
        logger.error("Invalid file type: %s", image_file.content_type)
        return {
            'success': False,
            'error': 'invalid_file_type',
            'message': 'Invalid file type. Please upload a JPG, PNG, or GIF image.',
            'status_code': 400
        }

    max_size = 5 * 1024 * 1024
    if image_file.size > max_size:
        logger.error("File too large: %s bytes", image_file.size)
        return {
            'success': False,
            'error': 'file_too_large',
            'message': 'File too large. Maximum size is 5MB.',
            'status_code': 400
        }

    try:
        # Convert image to base64
        image_data = image_file.read()
        base64_image = base64.b64encode(image_data).decode('utf-8')
        mime_type = image_file.content_type

        # Call GPT-4 Vision API
        logger.info("Calling GPT-4 Vision API")
        detected_ingredients = call_gpt_vision(base64_image, mime_type)

        if not detected_ingredients:
            logger.warning("No ingredients detected by GPT-4 Vision")
            return {
                'success': True,
                'detected_ingredients': [],
                'duplicates_removed': 0,
                'scans_remaining': scans_remaining - 1,
                'total_detected': 0,
                'message': (
                    'No ingredients detected. '
                    'The image may be too blurry or unclear.'
                )
            }

        logger.info("GPT-4 detected %s ingredients", len(detected_ingredients))

        # Validate ingredients with USDA
        logger.info("Validating ingredients with USDA API")
        usda_api_key = os.getenv('USDA_API_KEY')
        
        try:
            validator = USDAIngredientValidator(usda_api_key)
            validated_ingredients = validator.validate_ingredients(
                detected_ingredients
            )
        except ValueError as e:
            # API key not configured
            logger.error("USDA API key error: %s", str(e))
            return {
                'success': False,
                'error': 'configuration_error',
                'message': 'Service configuration error. Please contact support.',
                'status_code': 500
            }

        # Deduplicate against existing pantry
        unique_ingredients, duplicates_count = deduplicate_pantry_ingredients(
            request.user,
            validated_ingredients
        )

        logger.info("Removed %s duplicates", duplicates_count)

        # Record scan attempt
        ScanRateLimit.record_scan(request.user, get_client_ip(request))

        return {
            'success': True,
            'detected_ingredients': unique_ingredients,
            'duplicates_removed': duplicates_count,
            'scans_remaining': scans_remaining - 1,
            'total_detected': len(detected_ingredients)
        }

    except json.JSONDecodeError as e:
        logger.error("JSON decode error: %s", str(e))
        return {
            'success': False,
            'error': 'invalid_response',
            'message': 'Failed to process image analysis results.',
            'status_code': 500
        }
    except Exception as e:
        logger.exception("Unexpected error during pantry scan")
        return {
            'success': False,
            'error': 'internal_error',
            'message': 'An unexpected error occurred. Please try again.',
            'status_code': 500
        }


def call_gpt_vision(base64_image: str, mime_type: str) -> List[str]:
    """
    Call GPT-4 Vision API to extract ingredients from image.

    Args:
        base64_image: Base64-encoded image data
        mime_type: MIME type of the image

    Returns:
        List of ingredient names detected

    Raises:
        ValueError: If API key is not configured
        Exception: For API errors
    """
    api_key = os.getenv('OPENAI_API_KEY')

    if not api_key:
        raise ValueError("OpenAI API key not found in environment")

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """You are a pantry scanning assistant.
Analyze this image of a pantry or refrigerator and list all visible food items and ingredients.

Rules:
1. Return ONLY a JSON array of ingredient names
2. Include brand names if visible (e.g., "Jif Peanut Butter")
3. Be specific (e.g., "Chicken Breast" not just "Chicken")
4. Only include items you can clearly identify
5. Skip condiments, spices, and tiny items
6. Do not include any explanatory text, only the JSON array

Example output format:
["Chicken Breast", "Cheddar Cheese", "Whole Milk", "Banana", "Brown Rice"]
"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}",
                                "detail": "low"
                            }
                        }
                    ]
                }
            ],
            max_tokens=500,
            temperature=0.3
        )

        content = response.choices[0].message.content.strip()
        
        # Strip markdown code blocks
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # Parse and validate JSON
        try:
            ingredients = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse GPT-4 response as JSON: %s\nContent: %s",
                str(e),
                content
            )
            return []

        if not isinstance(ingredients, list):
            logger.error(
                "GPT-4 returned non-list response: %s",
                type(ingredients)
            )
            return []

        # Filter to ensure all items are strings
        valid_ingredients = [
            ing for ing in ingredients
            if isinstance(ing, str) and ing.strip()
        ]

        logger.info(
            "GPT-4 successfully extracted %s ingredients",
            len(valid_ingredients)
        )
        return valid_ingredients

    except Exception as e:
        logger.error("GPT-4 API request failed: %s", str(e))
        raise


def deduplicate_pantry_ingredients(user, validated_ingredients: List[Dict]):
    """
    Remove ingredients that already exist in user's pantry.

    Args:
        user: User object
        validated_ingredients: List of validated ingredient dicts

    Returns:
        Tuple of (unique_ingredients, duplicates_count)
    """
    pantry, _ = Pantry.objects.get_or_create(user=user)
    existing_ingredients = pantry.ingredients.all()

    existing_names = {
        f"{ing.name.lower()}|{ing.brand.lower()}"
        for ing in existing_ingredients
    }

    unique_ingredients = []
    duplicates_count = 0

    for ingredient in validated_ingredients:
        if not isinstance(ingredient, dict):
            logger.warning("Invalid ingredient format in deduplication")
            continue

        name = ingredient.get('name', '')
        brand = ingredient.get('brand', 'Generic')
        key = f"{name.lower()}|{brand.lower()}"

        if key not in existing_names:
            unique_ingredients.append(ingredient)
        else:
            duplicates_count += 1
            logger.debug("Duplicate found: %s", name)

    return unique_ingredients, duplicates_count


def add_ingredients_to_pantry(user, ingredients_data):
    """
    Add scanned ingredients to user's pantry.

    Args:
        user: User object
        ingredients_data: List of ingredient dictionaries

    Returns:
        dict: Response data with success status and added ingredients
    """
    added_ingredients = []
    allergen_cache = {}

    for ing_data in ingredients_data:
        if not isinstance(ing_data, dict):
            logger.warning("Invalid ingredient data format")
            continue

        try:
            name = ing_data.get('name', '').strip()
            brand = ing_data.get('brand', 'Generic').strip()
            calories = ing_data.get('calories', 0)

            if not name:
                logger.warning("Ingredient missing name, skipping")
                continue

            ingredient, created = Ingredient.objects.get_or_create(
                name=name,
                brand=brand,
                defaults={'calories': calories}
            )

            if not created and ingredient.calories != calories:
                ingredient.calories = calories

            # Fetch USDA nutrition data if fdc_id is provided
            fdc_id = ing_data.get('fdc_id')
            if fdc_id and not ingredient.has_nutrition_data():
                try:
                    logger.info(
                        "Fetching USDA data for scanned ingredient: %s (fdc_id: %s)",
                        ingredient.name,
                        fdc_id
                    )

                    complete_data = get_complete_ingredient_data(
                        fdc_id,
                        Allergen.objects.all()
                    )

                    # Store USDA data
                    ingredient.fdc_id = fdc_id
                    ingredient.nutrition_data = complete_data['nutrients']
                    ingredient.portion_data = complete_data['portions']

                    # Update calories from USDA if more accurate
                    if complete_data['basic']['calories_per_100g']:
                        ingredient.calories = int(
                            complete_data['basic']['calories_per_100g']
                        )

                    logger.info(
                        "Successfully stored USDA nutrition data for %s",
                        ingredient.name
                    )

                except usda_api.USDAAPIKeyError:
                    logger.error("Invalid USDA API key during scan")
                    # Continue without USDA data

                except usda_api.USDAAPIRateLimitError:
                    logger.warning(
                        "USDA rate limit hit for scanned ingredient %s",
                        ingredient.name
                    )
                    # Continue without USDA data

                except usda_api.USDAAPIError as e:
                    logger.error(
                        "USDA API error for %s (fdc_id: %s): %s",
                        ingredient.name,
                        fdc_id,
                        str(e)
                    )
                    # Continue without USDA data

                except Exception as e:
                    logger.exception(
                        "Unexpected error fetching USDA data for %s (fdc_id: %s)",
                        ingredient.name,
                        fdc_id
                    )
                    # Continue without USDA data

            # Save ingredient with potentially updated USDA data
            ingredient.save()

            # Set allergens
            allergen_names = ing_data.get('allergens', [])
            if isinstance(allergen_names, list) and allergen_names:
                allergens = []
                for allergen_name in allergen_names:
                    if not isinstance(allergen_name, str):
                        continue

                    if allergen_name not in allergen_cache:
                        allergen, _ = Allergen.objects.get_or_create(
                            name=allergen_name,
                            defaults={'category': 'fda_major_9'}
                        )
                        allergen_cache[allergen_name] = allergen
                    allergens.append(allergen_cache[allergen_name])

                ingredient.allergens.set(allergens)

            # Add to pantry
            pantry, _ = Pantry.objects.get_or_create(user=user)

            if ingredient not in pantry.ingredients.all():
                pantry.ingredients.add(ingredient)
                added_ingredients.append({
                    'id': ingredient.id,
                    'name': ingredient.name,
                    'brand': ingredient.brand,
                    'calories': ingredient.calories,
                    'has_nutrition_data': ingredient.has_nutrition_data()
                })

        except Exception as e:
            logger.exception(
                "Error adding ingredient %s",
                ing_data.get('name', 'unknown')
            )
            continue

    logger.info("Added %s ingredients to pantry", len(added_ingredients))

    return {
        'success': True,
        'added_count': len(added_ingredients),
        'ingredients': added_ingredients
    }
    