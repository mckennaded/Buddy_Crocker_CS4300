"""
Updated tests for USDA API with new error handling.

Tests now properly mock the session object and test new exception types.
"""

import os
import sys
import json
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.core.cache import cache
from django.urls import reverse
from dotenv import load_dotenv
from requests.exceptions import Timeout, ConnectionError as RequestsConnectionError
from services.ingredient_validator import USDAIngredientValidator
from buddy_crocker.models import Allergen, Ingredient, Pantry, Profile
from services import usda_api, usda_service

# Load environment
load_dotenv()


class SearchFoodsTest(TestCase):
    """Tests for the search_foods function with new error handling."""

    def setUp(self):
        """Clear the cache before each test."""
        cache.clear()

    def tearDown(self):
        """Clean up the cache after each test."""
        cache.clear()

    @patch('services.usda_api._session')
    def test_search_foods_success(self, mock_session):
        """Test successful search_foods API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'foods': [
                {
                    'description': 'Cheddar Cheese',
                    'dataType': 'Branded',
                    'fdcId': 123456,
                    'brandOwner': 'Generic Brand',
                    'foodNutrients': [
                        {'nutrientName': 'Energy', 'value': 403},
                        {'nutrientName': 'Protein', 'value': 25}
                    ]
                }
            ]
        }
        mock_session.get.return_value = mock_response

        foods = usda_api.search_foods("Cheddar Cheese", use_cache=False)

        self.assertEqual(len(foods), 1)
        self.assertEqual(foods[0]["description"], "Cheddar Cheese")
        self.assertEqual(foods[0]["fdcId"], 123456)

    @patch('services.usda_api._session')
    def test_search_foods_empty_results(self, mock_session):
        """Test search_foods with no results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'foods': []}
        mock_session.get.return_value = mock_response

        foods = usda_api.search_foods("NonexistentFood123", use_cache=False)

        self.assertEqual(len(foods), 0)

    @patch('services.usda_api._session')
    def test_search_foods_invalid_api_key(self, mock_session):
        """Test search_foods with invalid API key (403)."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_session.get.return_value = mock_response

        with self.assertRaises(usda_api.USDAAPIKeyError):
            usda_api.search_foods("Cheddar Cheese", use_cache=False)

    @patch('services.usda_api._session')
    def test_search_foods_rate_limiting(self, mock_session):
        """Test search_foods with rate limiting response (429)."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_session.get.return_value = mock_response

        with self.assertRaises(usda_api.USDAAPIRateLimitError):
            usda_api.search_foods("Cheddar Cheese", use_cache=False)

    @patch('services.usda_api._session')
    def test_search_foods_server_error(self, mock_session):
        """Test search_foods with server error (500+)."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_session.get.return_value = mock_response

        with self.assertRaises(usda_api.USDAAPIError):
            usda_api.search_foods("Cheddar Cheese", use_cache=False)

    @patch('services.usda_api._session')
    def test_search_foods_network_timeout(self, mock_session):
        """Test search_foods with network timeout."""
        mock_session.get.side_effect = Timeout("Connection timeout")

        with self.assertRaises(usda_api.USDAAPIError) as context:
            usda_api.search_foods("Cheddar Cheese", use_cache=False)

        self.assertIn("timeout", str(context.exception).lower())

    @patch('services.usda_api._session')
    def test_search_foods_connection_error(self, mock_session):
        """Test search_foods with connection error."""
        mock_session.get.side_effect = RequestsConnectionError("Network error")

        with self.assertRaises(usda_api.USDAAPIError) as context:
            usda_api.search_foods("Cheddar Cheese", use_cache=False)

        self.assertIn("Connection failed", str(context.exception))

    @patch('services.usda_api._session')
    def test_search_foods_invalid_json(self, mock_session):
        """Test search_foods with invalid JSON response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_session.get.return_value = mock_response

        with self.assertRaises(usda_api.USDAAPIValidationError):
            usda_api.search_foods("Cheddar Cheese", use_cache=False)

    @patch('services.usda_api._session')
    def test_search_foods_missing_foods_field(self, mock_session):
        """Test that missing 'foods' field raises validation error."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': []}  # Wrong field
        mock_session.get.return_value = mock_response

        with self.assertRaises(usda_api.USDAAPIValidationError):
            usda_api.search_foods("Cheddar Cheese", use_cache=False)

    @patch('services.usda_api._session')
    @patch('services.usda_api.cache')
    def test_search_foods_uses_cache(self, mock_cache, mock_session):
        """Test that search uses cache when available."""
        cached_data = [{'description': 'Cached Food'}]
        mock_cache.get.return_value = cached_data

        result = usda_api.search_foods("chicken", use_cache=True)

        # Should return cached result without making API call
        self.assertEqual(result, cached_data)
        mock_session.get.assert_not_called()

    @patch('services.usda_api._session')
    def test_search_foods_custom_page_size(self, mock_session):
        """Test search_foods with custom page size parameter."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'foods': []}
        mock_session.get.return_value = mock_response

        usda_api.search_foods("Cheddar Cheese", page_size=5, use_cache=False)

        # Verify the request was made with correct page_size
        call_kwargs = mock_session.get.call_args[1]
        self.assertEqual(call_kwargs['params']['pageSize'], 5)


class GetFoodDetailsTest(TestCase):
    """Tests for the get_food_details function with new error handling."""

    def setUp(self):
        """Clear the cache."""
        cache.clear()

    def tearDown(self):
        """Clean up the cache."""
        cache.clear()

    @patch('services.usda_api._session')
    def test_get_food_details_success(self, mock_session):
        """Test successful get_food_details API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'fdcId': 1897574,
            'description': 'Bacon, cooked',
            'dataType': 'SR Legacy',
            'brandOwner': 'USDA',
            'foodNutrients': [
                {
                    'nutrient': {'name': 'Energy', 'id': 1008},
                    'amount': 541
                }
            ]
        }
        mock_session.get.return_value = mock_response

        result = usda_api.get_food_details(1897574, use_cache=False)

        self.assertEqual(result['fdcId'], 1897574)
        self.assertEqual(result['description'], 'Bacon, cooked')

    @patch('services.usda_api._session')
    def test_get_food_details_not_found(self, mock_session):
        """Test get_food_details with invalid food ID (404)."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_session.get.return_value = mock_response

        with self.assertRaises(usda_api.USDAAPINotFoundError):
            usda_api.get_food_details(999999999, use_cache=False)

    @patch('services.usda_api._session')
    def test_get_food_details_missing_required_fields(self, mock_session):
        """Test validation of required fields."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'description': 'Test Food'
            # Missing fdcId and dataType
        }
        mock_session.get.return_value = mock_response

        with self.assertRaises(usda_api.USDAAPIValidationError):
            usda_api.get_food_details(123456, use_cache=False)

    @patch('services.usda_api._session')
    def test_get_food_details_network_error(self, mock_session):
        """Test get_food_details with network error."""
        mock_session.get.side_effect = RequestsConnectionError("Network error")

        with self.assertRaises(usda_api.USDAAPIError):
            usda_api.get_food_details(1897574, use_cache=False)

    @patch('services.usda_api._session')
    def test_get_food_details_rate_limiting(self, mock_session):
        """Test get_food_details with rate limiting."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_session.get.return_value = mock_response

        with self.assertRaises(usda_api.USDAAPIRateLimitError):
            usda_api.get_food_details(1897574, use_cache=False)


class GetCompleteFoodDataTest(TestCase):
    """Tests for get_complete_food_data with new error handling."""

    def setUp(self):
        """Clear the cache."""
        cache.clear()

    def tearDown(self):
        """Clean up the cache."""
        cache.clear()

    @patch('services.usda_api.get_food_details')
    def test_get_complete_food_data_success(self, mock_get_details):
        """Test successful retrieval of complete food data."""
        mock_get_details.return_value = {
            'fdcId': 123456,
            'description': 'Cheddar Cheese',
            'brandOwner': 'Generic Brand',
            'dataType': 'Branded',
            'ingredients': 'Pasteurized milk, salt, enzymes',
            'foodNutrients': [
                {
                    'nutrient': {'id': 1008, 'name': 'Energy', 'unitName': 'kcal'},
                    'amount': 403
                },
                {
                    'nutrient': {'id': 1003, 'name': 'Protein', 'unitName': 'g'},
                    'amount': 25
                }
            ],
            'foodPortions': [
                {
                    'id': 1,
                    'amount': 1,
                    'modifier': '',
                    'measureUnit': {'name': 'cup, diced'},
                    'gramWeight': 132,
                    'portionDescription': '1 cup, diced',
                    'sequenceNumber': 1
                }
            ]
        }

        result = usda_api.get_complete_food_data(123456, use_cache=False)

        # Check basic info
        self.assertEqual(result['basic']['name'], 'Cheddar Cheese')
        self.assertEqual(result['basic']['calories_per_100g'], 403)

        # Check nutrients
        self.assertIn('protein', result['nutrients']['macronutrients'])

        # Check portions
        self.assertEqual(len(result['portions']), 1)

    @patch('services.usda_api.get_food_details')
    def test_get_complete_food_data_propagates_exceptions(self, mock_get_details):
        """Test that exceptions from get_food_details propagate."""
        mock_get_details.side_effect = usda_api.USDAAPINotFoundError(
            "Food not found"
        )

        with self.assertRaises(usda_api.USDAAPINotFoundError):
            usda_api.get_complete_food_data(999999, use_cache=False)


class USDAIngredientValidatorTest(TestCase):
    """Updated tests for USDAIngredientValidator."""

    def setUp(self):
        """Set up test data."""
        self.validator = USDAIngredientValidator(api_key="test-key")
        self.allergen = Allergen.objects.create(
            name="Milk",
            category="fda_major_9",
            alternative_names=["dairy", "lactose", "casein"]
        )

    @patch('services.ingredient_validator.requests.get')
    def test_validate_single_ingredient_success(self, mock_get):
        """Test successful validation."""
        # Mock search response
        search_response = MagicMock()
        search_response.status_code = 200
        search_response.json.return_value = {
            "foods": [
                {
                    "description": "Cheddar Cheese",
                    "brandOwner": "Generic Brand",
                    "fdcId": 123456,
                    "dataType": "Branded",
                }
            ]
        }

        # Mock details response
        details_response = MagicMock()
        details_response.status_code = 200
        details_response.json.return_value = {
            "fdcId": 123456,
            "description": "Cheddar Cheese",
            "brandOwner": "Generic Brand",
            "dataType": "Branded",
            "foodNutrients": [
                {
                    "nutrient": {"id": 1008},
                    "amount": 403,
                }
            ],
            "ingredients": "Pasteurized milk, salt, enzymes.",
        }

        mock_get.side_effect = [search_response, details_response]

        result = self.validator._validate_single_ingredient("cheddar cheese")

        self.assertEqual(result["name"], "Cheddar Cheese")
        self.assertEqual(result["validation_status"], "success")
        self.assertIn("Milk", result["allergens"])

    @patch('services.ingredient_validator.requests.get')
    def test_validate_single_ingredient_not_found(self, mock_get):
        """Test validation when ingredient not found."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"foods": []}
        mock_get.return_value = mock_response

        result = self.validator._validate_single_ingredient("made-up-item-xyz")

        self.assertEqual(result["validation_status"], "not_found")
        self.assertEqual(result["calories"], 0)

    @patch('services.ingredient_validator.requests.get')
    def test_validate_handles_timeout(self, mock_get):
        """Test that validator handles timeouts."""
        mock_get.side_effect = Timeout("Request timeout")

        results = self.validator.validate_ingredients(["peanut butter"])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["validation_status"], "error")

class USDAAPIExceptionHandlingTest(TestCase):
    """Tests for specific exception types in USDA API."""

    @patch('services.usda_api._session')
    def test_search_foods_invalid_api_key(self, mock_session):
        """Test that 403 raises USDAAPIKeyError."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_session.get.return_value = mock_response

        with self.assertRaises(usda_api.USDAAPIKeyError) as context:
            usda_api.search_foods("chicken")

        self.assertIn("Invalid API key", str(context.exception))

    @patch('services.usda_api._session')
    def test_search_foods_rate_limit(self, mock_session):
        """Test that 429 raises USDAAPIRateLimitError."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_session.get.return_value = mock_response

        with self.assertRaises(usda_api.USDAAPIRateLimitError) as context:
            usda_api.search_foods("chicken")

        self.assertIn("Rate limit exceeded", str(context.exception))

    @patch('services.usda_api._session')
    def test_get_food_details_not_found(self, mock_session):
        """Test that 404 raises USDAAPINotFoundError."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_session.get.return_value = mock_response

        with self.assertRaises(usda_api.USDAAPINotFoundError) as context:
            usda_api.get_food_details(999999)

        self.assertIn("Resource not found", str(context.exception))

    @patch('services.usda_api._session')
    def test_search_foods_server_error(self, mock_session):
        """Test that 500+ raises USDAAPIError."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_session.get.return_value = mock_response

        with self.assertRaises(usda_api.USDAAPIError) as context:
            usda_api.search_foods("chicken")

        self.assertIn("Server error", str(context.exception))

    @patch('services.usda_api._session')
    def test_search_foods_timeout(self, mock_session):
        """Test that timeout is handled properly."""
        mock_session.get.side_effect = Timeout("Connection timeout")

        with self.assertRaises(usda_api.USDAAPIError) as context:
            usda_api.search_foods("chicken")

        self.assertIn("timeout", str(context.exception).lower())

    @patch('services.usda_api._session')
    def test_search_foods_connection_error(self, mock_session):
        """Test that connection errors are handled."""
        mock_session.get.side_effect = RequestsConnectionError("Network error")

        with self.assertRaises(usda_api.USDAAPIError) as context:
            usda_api.search_foods("chicken")

        self.assertIn("Connection failed", str(context.exception))


class USDAAPIValidationTest(TestCase):
    """Tests for response validation in USDA API."""

    @patch('services.usda_api._session')
    def test_search_foods_invalid_json(self, mock_session):
        """Test handling of invalid JSON response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_session.get.return_value = mock_response

        with self.assertRaises(usda_api.USDAAPIValidationError) as context:
            usda_api.search_foods("chicken")

        self.assertIn("Invalid JSON", str(context.exception))

    @patch('services.usda_api._session')
    def test_search_foods_missing_foods_field(self, mock_session):
        """Test handling of response missing 'foods' field."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": "some issue"}
        mock_session.get.return_value = mock_response

        with self.assertRaises(usda_api.USDAAPIError):
            usda_api.search_foods("chicken")

    @patch('services.usda_api._session')
    def test_search_foods_foods_not_list(self, mock_session):
        """Test handling when 'foods' is not a list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"foods": "not a list"}
        mock_session.get.return_value = mock_response

        with self.assertRaises(usda_api.USDAAPIValidationError) as context:
            usda_api.search_foods("chicken")

        self.assertIn("should be list", str(context.exception))

    @patch('services.usda_api._session')
    def test_get_food_details_missing_required_fields(self, mock_session):
        """Test validation of required fields in food details."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "description": "Test Food"
            # Missing fdcId and dataType
        }
        mock_session.get.return_value = mock_response

        with self.assertRaises(usda_api.USDAAPIValidationError) as context:
            usda_api.get_food_details(123456)

        self.assertIn("missing required fields", str(context.exception))


class USDAParsingValidationTest(TestCase):
    """Tests for validation in data parsing functions."""

    def test_parse_basic_info_invalid_data_type(self):
        """Test _parse_basic_info handles non-dict food_data."""
        result = usda_api._parse_basic_info("not a dict", 123456)

        self.assertEqual(result['calories_per_100g'], 0)
        self.assertEqual(result['name'], '')

    def test_parse_basic_info_invalid_nutrients_type(self):
        """Test handling when foodNutrients is not a list."""
        food_data = {
            'description': 'Test',
            'brandOwner': 'Generic',
            'dataType': 'Branded',
            'foodNutrients': "not a list"
        }

        result = usda_api._parse_basic_info(food_data, 123456)

        # Should default to 0 calories
        self.assertEqual(result['calories_per_100g'], 0)

    def test_parse_basic_info_invalid_calorie_value(self):
        """Test handling of invalid calorie values."""
        food_data = {
            'description': 'Test',
            'foodNutrients': [
                {
                    'nutrient': {'id': 1008},
                    'amount': "not a number"
                }
            ]
        }

        result = usda_api._parse_basic_info(food_data, 123456)

        # Should default to 0 for invalid value
        self.assertEqual(result['calories_per_100g'], 0)

    def test_parse_nutrients_invalid_structure(self):
        """Test _parse_nutrients handles invalid nutrient structures."""
        food_data = {
            'foodNutrients': [
                "not a dict",
                {'nutrient': "not a dict"},
                {
                    'nutrient': {'id': 1003},
                    'amount': "invalid"
                }
            ]
        }

        result = usda_api._parse_nutrients(food_data)

        # Should return empty categories
        self.assertEqual(result['macronutrients'], {})

    def test_parse_portions_invalid_structure(self):
        """Test _parse_portions handles invalid portion structures."""
        food_data = {
            'foodPortions': [
                "not a dict",
                {
                    'measureUnit': {'name': 'cup'},
                    'gramWeight': "invalid",
                    'amount': 1
                }
            ]
        }

        result = usda_api._parse_portions(food_data)

        # Should return empty list (invalid portions skipped)
        self.assertEqual(len(result), 0)


class ViewsErrorHandlingTest(TestCase):
    """Tests for error handling in views."""

    def setUp(self):
        """Set up test client and user."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        Profile.objects.filter(user=self.user).delete()
        self.allergen = Allergen.objects.create(
            name='Dairy',
            category='fda_major_9'
        )

    @patch('services.usda_service.get_complete_ingredient_data')
    def test_add_ingredient_handles_api_key_error(self, mock_get_data):
        """Test that add_ingredient handles API key errors gracefully."""
        self.client.login(username='testuser', password='testpass123')

        mock_get_data.side_effect = usda_api.USDAAPIKeyError("Invalid API key")

        response = self.client.post(
            reverse('add-ingredient'),
            {
                'name': 'Test Item',
                'brand': 'Generic',
                'calories': 100,
                'allergens': [],
                'fdc_id': '123456'
            }
        )

        # Should return form with error message
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertTrue(
            any('Configuration error' in str(m) for m in messages)
        )

    @patch('services.usda_service.get_complete_ingredient_data')
    def test_add_ingredient_handles_rate_limit(self, mock_get_data):
        """Test that add_ingredient handles rate limits gracefully."""
        self.client.login(username='testuser', password='testpass123')

        mock_get_data.side_effect = usda_api.USDAAPIRateLimitError(
            "Rate limit exceeded"
        )

        response = self.client.post(
            reverse('add-ingredient'),
            {
                'name': 'Test Item',
                'brand': 'Generic',
                'calories': 100,
                'allergens': [],
                'fdc_id': '123456'
            }
        )

        # Should succeed but show warning
        self.assertEqual(response.status_code, 302)

        # Verify ingredient was created
        ingredient = Ingredient.objects.get(name='Test Item')
        self.assertIsNotNone(ingredient)

    @patch('services.usda_service.get_complete_ingredient_data')
    def test_add_ingredient_handles_not_found(self, mock_get_data):
        """Test that add_ingredient handles 404 errors gracefully."""
        self.client.login(username='testuser', password='testpass123')

        mock_get_data.side_effect = usda_api.USDAAPINotFoundError(
            "Food not found"
        )

        response = self.client.post(
            reverse('add-ingredient'),
            {
                'name': 'Test Item',
                'brand': 'Generic',
                'calories': 100,
                'allergens': [],
                'fdc_id': '999999'
            }
        )

        # Should succeed but show warning
        self.assertEqual(response.status_code, 302)

    @patch('services.usda_service.search_usda_foods')
    def test_search_endpoint_handles_api_key_error(self, mock_search):
        """Test that search endpoint handles API key errors."""
        mock_search.side_effect = usda_api.USDAAPIKeyError("Invalid API key")

        response = self.client.get(
            reverse('search-usda-ingredients'),
            {'q': 'chicken'}
        )

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'configuration_error')
        self.assertIn('contact support', data['message'].lower())

    @patch('services.usda_service.search_usda_foods')
    def test_search_endpoint_handles_rate_limit(self, mock_search):
        """Test that search endpoint handles rate limits."""
        mock_search.side_effect = usda_api.USDAAPIRateLimitError(
            "Rate limit exceeded"
        )

        response = self.client.get(
            reverse('search-usda-ingredients'),
            {'q': 'chicken'}
        )

        self.assertEqual(response.status_code, 429)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'rate_limit_exceeded')

    @patch('services.usda_service.search_usda_foods')
    def test_search_endpoint_handles_generic_api_error(self, mock_search):
        """Test that search endpoint handles generic API errors."""
        mock_search.side_effect = usda_api.USDAAPIError("API Error")

        response = self.client.get(
            reverse('search-usda-ingredients'),
            {'q': 'chicken'}
        )

        self.assertEqual(response.status_code, 503)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'search_failed')


class ScanServiceErrorHandlingTest(TestCase):
    """Tests for error handling in scan service."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='scanuser',
            password='testpass123'
        )
        Profile.objects.filter(user=self.user).delete()

    @patch('services.scan_service.get_complete_ingredient_data')
    def test_add_scanned_ingredients_handles_api_key_error(self, mock_get_data):
        """Test that scan continues despite API key errors."""
        mock_get_data.side_effect = usda_api.USDAAPIKeyError("Invalid API key")

        from services.scan_service import add_ingredients_to_pantry

        ingredients_data = [
            {
                'name': 'Test Item',
                'brand': 'Generic',
                'calories': 100,
                'allergens': [],
                'fdc_id': 123456
            }
        ]

        result = add_ingredients_to_pantry(self.user, ingredients_data)

        # Should succeed (ingredient added without USDA data)
        self.assertTrue(result['success'])
        self.assertEqual(result['added_count'], 1)

    @patch('services.scan_service.get_complete_ingredient_data')
    def test_add_scanned_ingredients_handles_rate_limit(self, mock_get_data):
        """Test that scan continues despite rate limits."""
        mock_get_data.side_effect = usda_api.USDAAPIRateLimitError(
            "Rate limit exceeded"
        )

        from services.scan_service import add_ingredients_to_pantry

        ingredients_data = [
            {
                'name': 'Test Item',
                'brand': 'Generic',
                'calories': 100,
                'allergens': [],
                'fdc_id': 123456
            }
        ]

        result = add_ingredients_to_pantry(self.user, ingredients_data)

        # Should succeed
        self.assertTrue(result['success'])
        self.assertEqual(result['added_count'], 1)


class RetryLogicTest(TestCase):
    """Tests for retry logic in API calls."""

    @patch('services.usda_api._session')
    def test_session_has_retry_adapter(self, mock_session):
        """Test that session is configured with retry logic."""
        # Import to trigger session creation
        from services import usda_api

        # The _create_session_with_retries function should have been called
        # We can't easily test the retry behavior in unit tests,
        # but we can verify the function exists and returns a session
        session = usda_api._create_session_with_retries()

        self.assertIsNotNone(session)
        # Check that adapters are mounted
        self.assertIn('https://', session.adapters)


class DataValidationTest(TestCase):
    """Tests for data validation in service functions."""

    def test_detect_allergens_handles_none_input(self):
        """Test that allergen detection handles None input."""
        result = usda_service.detect_allergens_from_name(None, [])
        self.assertEqual(result, [])

    def test_detect_allergens_handles_empty_string(self):
        """Test that allergen detection handles empty string."""
        result = usda_service.detect_allergens_from_name("", [])
        self.assertEqual(result, [])

    def test_detect_allergens_handles_invalid_alternatives(self):
        """Test that allergen detection handles invalid alternative names."""
        allergen = Allergen.objects.create(
            name="Dairy",
            alternative_names="not a list"  # Invalid
        )

        result = usda_service.detect_allergens_from_name(
            "milk chocolate",
            [allergen]
        )

        # Should still detect from main name
        self.assertEqual(len(result), 0)  # Doesn't contain "Dairy"

    def test_format_nutrient_display_handles_invalid_input(self):
        """Test that nutrient formatting handles invalid input."""
        result = usda_service.format_nutrient_display("not a dict")

        # Should return empty structure
        self.assertEqual(result['macronutrients'], [])

    def test_calculate_portion_calories_handles_invalid_input(self):
        """Test that calculation handles invalid input."""
        result = usda_service.calculate_portion_calories("invalid", 100)
        self.assertEqual(result, 0)

        result = usda_service.calculate_portion_calories(100, "invalid")
        self.assertEqual(result, 0)


class CachingBehaviorTest(TestCase):
    """Tests for caching behavior."""

    @patch('services.usda_api._session')
    @patch('services.usda_api.cache')
    def test_search_foods_uses_cache(self, mock_cache, mock_session):
        """Test that search uses cache when available."""
        mock_cache.get.return_value = [{'description': 'Cached Food'}]

        result = usda_api.search_foods("chicken", use_cache=True)

        # Should return cached result without making API call
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['description'], 'Cached Food')
        mock_session.get.assert_not_called()

    @patch('services.usda_api._session')
    @patch('services.usda_api.cache')
    def test_search_foods_bypasses_cache_when_disabled(
        self,
        mock_cache,
        mock_session
    ):
        """Test that search bypasses cache when use_cache=False."""
        mock_cache.get.return_value = [{'description': 'Cached Food'}]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'foods': [{'description': 'Fresh Food'}]
        }
        mock_session.get.return_value = mock_response

        result = usda_api.search_foods("chicken", use_cache=False)

        # Should make API call and not use cache
        mock_session.get.assert_called_once()
        mock_cache.get.assert_not_called()


class USDAAPIBaseTest(TestCase):
    """Base test class that mocks USDA_API_KEY environment variable."""
    
    def setUp(self):
        """Set up mock API key for all USDA tests."""
        super().setUp()
        self.env_patcher = patch.dict(os.environ, {'USDA_API_KEY': 'test-key'})
        self.env_patcher.start()
    
    def tearDown(self):
        """Clean up environment mock."""
        self.env_patcher.stop()
        super().tearDown()

        
class EdgeCaseTest(TestCase):
    """Tests for edge cases and boundary conditions."""

    def test_empty_ingredient_name_in_scan(self):
        """Test that scan handles empty ingredient names."""
        from services.scan_service import add_ingredients_to_pantry

        user = User.objects.create_user(username='test', password='test')
        Profile.objects.filter(user=user).delete()

        ingredients_data = [
            {
                'name': '',  # Empty name
                'brand': 'Generic',
                'calories': 100
            }
        ]

        result = add_ingredients_to_pantry(user, ingredients_data)

        # Should skip invalid ingredient
        self.assertTrue(result['success'])
        self.assertEqual(result['added_count'], 0)

    def test_invalid_ingredient_data_format_in_scan(self):
        """Test that scan handles invalid data formats."""
        from services.scan_service import add_ingredients_to_pantry

        user = User.objects.create_user(username='test', password='test')
        Profile.objects.filter(user=user).delete()

        ingredients_data = [
            "not a dict",
            {'name': 'Valid Item', 'brand': 'Generic', 'calories': 100}
        ]

        result = add_ingredients_to_pantry(user, ingredients_data)

        # Should skip invalid item and process valid one
        self.assertTrue(result['success'])
        self.assertEqual(result['added_count'], 1)
