# services/ingredient_validator.py
# pylint: disable=too-few-public-methods
"""
USDA Ingredient Validator Service

Validates ingredients against USDA FoodData Central API and extracts
accurate nutritional and allergen information.
"""

import logging
from typing import List, Dict, Optional
import requests
from requests.exceptions import RequestException, Timeout

# Configure logging
logger = logging.getLogger(__name__)


class USDAIngredientValidator:
    """
    Validates ingredients using USDA FoodData Central API.
    
    Extracts nutritional information and detects allergens from ingredient data.
    """
    # USDA API configuration
    BASE_URL = "https://api.nal.usda.gov/fdc/v1"
    SEARCH_ENDPOINT = f"{BASE_URL}/foods/search"
    DETAILS_ENDPOINT = f"{BASE_URL}/food"

    # Data type priority for search results
    DATA_TYPE_PRIORITY = ["SR Legacy", "Survey (FNDDS)", "Branded"]

    # Energy nutrient ID in USDA database
    ENERGY_NUTRIENT_ID = 1008

    # Request timeout in seconds
    TIMEOUT = 3

    # Common allergens to check against (FDA Major 9)
    COMMON_ALLERGENS = [
        'milk', 'dairy', 'lactose', 'casein', 'whey', 'cream', 'butter', 'cheese',
        'egg', 'eggs', 'albumin', 'ovalbumin',
        'fish', 'salmon', 'tuna', 'cod', 'halibut', 'tilapia',
        'shellfish', 'shrimp', 'crab', 'lobster', 'clam', 'oyster', 'mussel',
        'tree nut', 'almond', 'walnut', 'cashew', 'pecan', 'pistachio', 'macadamia',
        'peanut', 'peanuts', 'groundnut',
        'wheat', 'gluten', 'flour',
        'soy', 'soya', 'soybean', 'tofu', 'edamame',
        'sesame', 'tahini'
    ]

    def __init__(self, api_key: str):
        """
        Initialize validator with API key.
        
        Args:
            api_key: USDA FoodData Central API key
        """
        if not api_key:
            raise ValueError("USDA API key is required")

        self.api_key = api_key
        logger.info("USDAIngredientValidator initialized")

    def validate_ingredients(
        self,
        ingredient_names: List[str]
    ) -> List[Dict]:
        """
        Validate multiple ingredients and retrieve their data.
        
        Args:
            ingredient_names: List of ingredient names to validate
            
        Returns:
            List of dictionaries containing validated ingredient data:
            {
                'name': str,
                'brand': str,
                'calories': int,
                'allergens': List[str],
                'fdc_id': int,
                'data_type': str,
                'validation_status': str,  # 'success', 'not_found', 'error'
                'validation_notes': str
            }
        """
        logger.info("Validating %s ingredients", len(ingredient_names))
        validated_ingredients = []

        for ingredient_name in ingredient_names:
            try:
                result = self._validate_single_ingredient(ingredient_name)
                validated_ingredients.append(result)
            except Exception as e: # pylint: disable=broad-exception-caught
                logger.error("Error validating ingredient '%s': %s", ingredient_name, str(e))
                validated_ingredients.append({
                    'name': ingredient_name,
                    'brand': 'Generic',
                    'calories': 0,
                    'allergens': [],
                    'fdc_id': None,
                    'data_type': None,
                    'validation_status': 'error',
                    'validation_notes': f'Validation error: {str(e)}'
                })

        logger.info("Successfully validated %s ingredients", len(validated_ingredients))
        return validated_ingredients

    def _validate_single_ingredient(self, ingredient_name: str) -> Dict:
        """
        Validate a single ingredient.
        
        Args:
            ingredient_name: Name of ingredient to validate
            
        Returns:
            Dictionary with ingredient data
        """
        logger.debug("Validating ingredient: %s", ingredient_name)

        # Search for the ingredient
        search_results = self._search_usda(ingredient_name)

        if not search_results:
            logger.warning("No results found for ingredient: %s", ingredient_name)
            return {
                'name': ingredient_name,
                'brand': 'Generic',
                'calories': 0,
                'allergens': [],
                'fdc_id': None,
                'data_type': None,
                'validation_status': 'not_found',
                'validation_notes': 'Ingredient not found in USDA database'
            }

        # Get the best match (first result with priority data type)
        best_match = self._select_best_match(search_results)

        # Get detailed information
        fdc_id = best_match.get('fdcId')
        details = self._get_food_details(fdc_id) if fdc_id else best_match

        # Extract data
        name = details.get('description', ingredient_name)
        brand = details.get('brandOwner', 'Generic') or 'Generic'
        calories = self._extract_nutrient(details, self.ENERGY_NUTRIENT_ID)
        allergens = self._extract_allergens(details)
        data_type = details.get('dataType', 'Unknown')

        return {
            'name': name,
            'brand': brand,
            'calories': int(calories) if calories else 0,
            'allergens': allergens,
            'fdc_id': fdc_id,
            'data_type': data_type,
            'validation_status': 'success',
            'validation_notes': f'Validated via USDA ({data_type})'
        }

    def _search_usda(self, query: str, page_size: int = 5) -> List[Dict]:
        """
        Search USDA database for ingredient.
        
        Args:
            query: Search query
            page_size: Number of results to return
            
        Returns:
            List of food items from USDA
        """
        params = {
            'api_key': self.api_key,
            'query': query,
            'pageSize': page_size,
            'dataType': self.DATA_TYPE_PRIORITY
        }

        try:
            logger.debug("Searching USDA API: %s", query)
            response = requests.get(
                self.SEARCH_ENDPOINT,
                params=params,
                timeout=self.TIMEOUT
            )
            response.raise_for_status()

            data = response.json()
            foods = data.get('foods', [])
            logger.debug("Found %s results for: %s", len(foods), query)
            return foods

        except Timeout as exc:
            logger.error("USDA API timeout for query: %s", query)
            raise RequestException(f"USDA API timeout (>{self.TIMEOUT}s)") from exc
        except RequestException as e:
            logger.error("USDA API request failed: %s", str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error during USDA search: %s", str(e))
            raise

    def _get_food_details(self, fdc_id: int) -> Optional[Dict]:
        """
        Get detailed food information by FDC ID.
        
        Args:
            fdc_id: USDA Food Data Central ID
            
        Returns:
            Food details dictionary or None
        """
        url = f"{self.DETAILS_ENDPOINT}/{fdc_id}"
        params = {'api_key': self.api_key}

        try:
            logger.debug("Fetching food details for FDC ID: %s", fdc_id)
            response = requests.get(url, params=params, timeout=self.TIMEOUT)
            response.raise_for_status()
            return response.json()
        except Timeout:
            logger.error("USDA API timeout for FDC ID: %s", fdc_id)
            return None
        except RequestException as e:
            logger.error("Failed to get food details for %s: %s", fdc_id, str(e))
            return None

    def _select_best_match(self, search_results: List[Dict]) -> Dict:
        """
        Select the best match from search results based on data type priority.
        
        Args:
            search_results: List of search results
            
        Returns:
            Best matching food item
        """
        if not search_results:
            return {}

        # Try to find a result matching priority data types
        for data_type in self.DATA_TYPE_PRIORITY:
            for result in search_results:
                if result.get('dataType') == data_type:
                    logger.debug("Selected match with data type: %s", data_type)
                    return result

        # Return first result if no priority match
        logger.debug("No priority match found, using first result")
        return search_results[0]

    def _extract_nutrient(
        self,
        food_data: Dict,
        nutrient_id: int
    ) -> Optional[float]:
        """
        Extract specific nutrient value from food data.
        
        Args:
            food_data: Food data dictionary
            nutrient_id: USDA nutrient ID to extract
            
        Returns:
            Nutrient value (per 100g) or None
        """
        food_nutrients = food_data.get('foodNutrients', [])

        for nutrient in food_nutrients:
            # Handle different response formats
            nutrient_info = nutrient.get('nutrient', {})
            nutrient_id_field = nutrient_info.get('id') or nutrient.get('nutrientId')

            if nutrient_id_field == nutrient_id:
                # Try different value field names
                value = (
                    nutrient.get('amount') or
                    nutrient.get('value') or
                    0
                )
                logger.debug("Extracted nutrient %s: %s", nutrient_id, value)
                return float(value) if value else 0

        logger.warning("Nutrient %s not found in food data", nutrient_id)
        return None

    def _extract_allergens(self, food_data: Dict) -> List[str]:
        """
        Extract allergens from food data by checking ingredients field.
        
        Args:
            food_data: Food data dictionary
            
        Returns:
            List of detected allergen names
        """
        detected_allergens = set()

        # Check ingredients field (common in branded foods)
        ingredients = food_data.get('ingredients', '').lower()
        description = food_data.get('description', '').lower()

        # Combine text to search
        search_text = f"{ingredients} {description}"

        # Check against common allergens
        for allergen in self.COMMON_ALLERGENS:
            if allergen in search_text:
                # Map to standard allergen names (FDA Major 9)
                standardized = self._standardize_allergen_name(allergen)
                if standardized:
                    detected_allergens.add(standardized)

        allergen_list = sorted(list(detected_allergens))
        if allergen_list:
            logger.debug("Detected allergens: %s", allergen_list)

        return allergen_list

    def _standardize_allergen_name(self, allergen_term: str) -> Optional[str]:
        """
        Standardize allergen term to FDA Major 9 category.
        
        Args:
            allergen_term: Raw allergen term
            
        Returns:
            Standardized allergen name or None
        """
        allergen_map = {
            # Milk/Dairy
            'milk': 'Milk', 'dairy': 'Milk', 'lactose': 'Milk',
            'casein': 'Milk', 'whey': 'Milk', 'cream': 'Milk',
            'butter': 'Milk', 'cheese': 'Milk',

            # Eggs
            'egg': 'Eggs', 'eggs': 'Eggs', 'albumin': 'Eggs',
            'ovalbumin': 'Eggs',

            # Fish
            'fish': 'Fish', 'salmon': 'Fish', 'tuna': 'Fish',
            'cod': 'Fish', 'halibut': 'Fish', 'tilapia': 'Fish',

            # Shellfish
            'shellfish': 'Shellfish', 'shrimp': 'Shellfish', 'crab': 'Shellfish',
            'lobster': 'Shellfish', 'clam': 'Shellfish', 'oyster': 'Shellfish',
            'mussel': 'Shellfish',

            # Tree Nuts
            'tree nut': 'Tree Nuts', 'almond': 'Tree Nuts', 'walnut': 'Tree Nuts',
            'cashew': 'Tree Nuts', 'pecan': 'Tree Nuts', 'pistachio': 'Tree Nuts',
            'macadamia': 'Tree Nuts',

            # Peanuts
            'peanut': 'Peanuts', 'peanuts': 'Peanuts', 'groundnut': 'Peanuts',

            # Wheat/Gluten
            'wheat': 'Wheat', 'gluten': 'Wheat', 'flour': 'Wheat',

            # Soy
            'soy': 'Soybeans', 'soya': 'Soybeans', 'soybean': 'Soybeans',
            'tofu': 'Soybeans', 'edamame': 'Soybeans',

            # Sesame
            'sesame': 'Sesame', 'tahini': 'Sesame'
        }

        return allergen_map.get(allergen_term.lower())


# Example usage:
# validator = USDAIngredientValidator(api_key="your_api_key")
# results = validator.validate_ingredients(["chicken breast", "cheddar cheese", "banana"])
