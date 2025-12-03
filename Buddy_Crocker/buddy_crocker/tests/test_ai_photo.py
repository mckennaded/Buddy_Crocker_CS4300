"""
Unit and integration tests for the pantry scanning feature.

Tests the scan endpoints, rate limiting, USDA validation, and integration.
"""
import os
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from io import BytesIO
from PIL import Image

from buddy_crocker.models import Ingredient, Allergen, Pantry, ScanRateLimit
from services.ingredient_validator import USDAIngredientValidator


class ScanRateLimitModelTest(TestCase):
    """Test cases for ScanRateLimit model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_rate_limit_creation(self):
        """Test that scan rate limit records can be created."""
        scan = ScanRateLimit.objects.create(
            user=self.user,
            ip_address='127.0.0.1'
        )
        self.assertIsNotNone(scan.pk)
        self.assertEqual(scan.user, self.user)
        self.assertEqual(scan.ip_address, '127.0.0.1')

    def test_check_rate_limit_allowed(self):
        """Test rate limit check when user hasn't exceeded limit."""
        is_allowed, scans_remaining, reset_time = (
            ScanRateLimit.check_rate_limit(
                self.user,
                max_scans=5,
                time_window_minutes=5
            )
        )

        self.assertTrue(is_allowed)
        self.assertEqual(scans_remaining, 5)
        self.assertIsNone(reset_time)

    def test_check_rate_limit_exceeded(self):
        """Test rate limit check when user has exceeded limit."""
        for _ in range(5):
            ScanRateLimit.objects.create(user=self.user)

        is_allowed, scans_remaining, reset_time = (
            ScanRateLimit.check_rate_limit(
                self.user,
                max_scans=5,
                time_window_minutes=5
            )
        )

        self.assertFalse(is_allowed)
        self.assertEqual(scans_remaining, 0)
        self.assertIsNotNone(reset_time)

    def test_check_rate_limit_expired_scans(self):
        """Test that old scans outside time window don't count."""
        old_scan = ScanRateLimit.objects.create(user=self.user)
        old_scan.timestamp = timezone.now() - timedelta(minutes=6)
        old_scan.save()

        is_allowed, scans_remaining, _ = ScanRateLimit.check_rate_limit(
            self.user,
            max_scans=5,
            time_window_minutes=5
        )

        self.assertTrue(is_allowed)
        self.assertEqual(scans_remaining, 5)

    def test_record_scan(self):
        """Test recording a scan attempt."""
        scan = ScanRateLimit.record_scan(self.user, '127.0.0.1')

        self.assertIsNotNone(scan.pk)
        self.assertEqual(scan.user, self.user)
        self.assertEqual(scan.ip_address, '127.0.0.1')

    def test_cleanup_old_records(self):
        """Test cleanup of old scan records."""
        old_scan = ScanRateLimit.objects.create(user=self.user)
        old_scan.timestamp = timezone.now() - timedelta(days=8)
        old_scan.save()

        ScanRateLimit.objects.create(user=self.user)

        deleted_count = ScanRateLimit.cleanup_old_records(days=7)

        self.assertEqual(deleted_count, 1)
        self.assertEqual(ScanRateLimit.objects.count(), 1)


class USDAIngredientValidatorTest(TestCase):
    """Test cases for USDAIngredientValidator service."""

    def setUp(self):
        self.api_key = os.getenv('USDA_API_KEY', 'test_key')
        self.validator = USDAIngredientValidator(self.api_key)

    def test_validator_initialization(self):
        """Test that validator initializes with API key."""
        self.assertEqual(self.validator.api_key, self.api_key)

    def test_validator_requires_api_key(self):
        """Test that validator requires an API key."""
        with self.assertRaises(ValueError):
            USDAIngredientValidator(api_key=None)

    @patch('services.ingredient_validator.requests.get')
    def test_search_usda_success(self, mock_get):
        """Test successful USDA search."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'foods': [
                {
                    'description': 'Chicken Breast',
                    'fdcId': 123456,
                    'dataType': 'SR Legacy',
                    'brandOwner': None
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        results = self.validator._search_usda('chicken')

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['description'], 'Chicken Breast')

    @patch('services.ingredient_validator.requests.get')
    def test_search_usda_timeout(self, mock_get):
        """Test USDA search timeout handling."""
        from requests.exceptions import Timeout
        mock_get.side_effect = Timeout()

        with self.assertRaises(Exception):
            self.validator._search_usda('chicken')

    def test_extract_nutrient(self):
        """Test nutrient extraction from food data."""
        food_data = {
            'foodNutrients': [
                {
                    'nutrient': {'id': 1008, 'name': 'Energy'},
                    'amount': 165
                }
            ]
        }

        calories = self.validator._extract_nutrient(food_data, 1008)
        self.assertEqual(calories, 165)

    def test_extract_allergens(self):
        """Test allergen extraction from food data."""
        food_data = {
            'description': 'Peanut Butter',
            'ingredients': 'roasted peanuts, salt'
        }

        allergens = self.validator._extract_allergens(food_data)
        self.assertIn('Peanuts', allergens)

    def test_standardize_allergen_name(self):
        """Test allergen name standardization."""
        self.assertEqual(
            self.validator._standardize_allergen_name('milk'),
            'Milk'
        )
        self.assertEqual(
            self.validator._standardize_allergen_name('peanut'),
            'Peanuts'
        )
        self.assertEqual(
            self.validator._standardize_allergen_name('soy'),
            'Soybeans'
        )

    @patch.object(USDAIngredientValidator, '_search_usda')
    @patch.object(USDAIngredientValidator, '_get_food_details')
    def test_validate_single_ingredient_success(self, mock_details, mock_search):
        """Test successful ingredient validation."""
        mock_search.return_value = [
            {
                'description': 'Chicken Breast',
                'fdcId': 123456,
                'dataType': 'SR Legacy',
                'brandOwner': None,
                'foodNutrients': [
                    {'nutrient': {'id': 1008}, 'amount': 165}
                ]
            }
        ]
        mock_details.return_value = mock_search.return_value[0]

        result = self.validator._validate_single_ingredient('chicken breast')

        self.assertEqual(result['name'], 'Chicken Breast')
        self.assertEqual(result['calories'], 165)
        self.assertEqual(result['validation_status'], 'success')

    @patch.object(USDAIngredientValidator, '_search_usda')
    def test_validate_single_ingredient_not_found(self, mock_search):
        """Test ingredient validation when not found."""
        mock_search.return_value = []

        result = self.validator._validate_single_ingredient('nonexistent')

        self.assertEqual(result['validation_status'], 'not_found')
        self.assertEqual(result['calories'], 0)


class ScanPantryViewTest(TestCase):
    """Test cases for scan_pantry endpoint."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        Pantry.objects.create(user=self.user)

    def _create_test_image(self):
        """Create a test image file."""
        file = BytesIO()
        image = Image.new('RGB', (100, 100), color='red')
        image.save(file, 'PNG')
        file.name = 'test.png'
        file.seek(0)
        return file

    def test_scan_pantry_requires_login(self):
        """Test that scan endpoint requires authentication."""
        self.client.logout()
        response = self.client.post(reverse('scan-pantry'))
        self.assertEqual(response.status_code, 302)

    def test_scan_pantry_requires_image(self):
        """Test that scan endpoint requires image file."""
        response = self.client.post(reverse('scan-pantry'))

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('no_image', data['error'])

    def test_scan_pantry_validates_file_type(self):
        """Test that scan endpoint validates file type."""
        file = BytesIO(b'not an image')
        file.name = 'test.txt'
        file.content_type = 'text/plain'

        response = self.client.post(
            reverse('scan-pantry'),
            {'image': file}
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('invalid_file_type', data['error'])

    @patch('services.scan_service.call_gpt_vision')
    @patch('services.scan_service.USDAIngredientValidator')
    def test_scan_pantry_success(self, mock_validator_class, mock_gpt):
        """Test successful pantry scan."""
        mock_gpt.return_value = ['Chicken Breast', 'Banana']

        mock_validator = MagicMock()
        mock_validator.validate_ingredients.return_value = [
            {
                'name': 'Chicken Breast',
                'brand': 'Generic',
                'calories': 165,
                'allergens': [],
                'validation_status': 'success'
            },
            {
                'name': 'Banana',
                'brand': 'Generic',
                'calories': 89,
                'allergens': [],
                'validation_status': 'success'
            }
        ]
        mock_validator_class.return_value = mock_validator

        image = self._create_test_image()
        response = self.client.post(
            reverse('scan-pantry'),
            {'image': image}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['detected_ingredients']), 2)
        self.assertEqual(data['total_detected'], 2)

    def test_scan_pantry_rate_limiting(self):
        """Test that rate limiting is enforced."""
        for _ in range(5):
            ScanRateLimit.objects.create(user=self.user)

        image = self._create_test_image()
        response = self.client.post(
            reverse('scan-pantry'),
            {'image': image}
        )

        self.assertEqual(response.status_code, 429)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('rate_limit_exceeded', data['error'])

    @patch('services.scan_service.call_gpt_vision')
    @patch('services.scan_service.USDAIngredientValidator')
    def test_scan_pantry_deduplication(self, mock_validator_class, mock_gpt):
        """Test that duplicates are removed from scan results."""
        existing_ingredient = Ingredient.objects.create(
            name='Chicken Breast',
            brand='Generic',
            calories=165
        )
        pantry = Pantry.objects.get(user=self.user)
        pantry.ingredients.add(existing_ingredient)

        mock_gpt.return_value = ['Chicken Breast', 'Banana']
        mock_validator = MagicMock()
        mock_validator.validate_ingredients.return_value = [
            {
                'name': 'Chicken Breast',
                'brand': 'Generic',
                'calories': 165,
                'allergens': []
            },
            {
                'name': 'Banana',
                'brand': 'Generic',
                'calories': 89,
                'allergens': []
            }
        ]
        mock_validator_class.return_value = mock_validator

        image = self._create_test_image()
        response = self.client.post(
            reverse('scan-pantry'),
            {'image': image}
        )

        data = json.loads(response.content)
        self.assertEqual(len(data['detected_ingredients']), 1)
        self.assertEqual(data['duplicates_removed'], 1)


class AddScannedIngredientsViewTest(TestCase):
    """Test cases for add_scanned_ingredients endpoint."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

        Pantry.objects.create(user=self.user)

        self.peanuts = Allergen.objects.create(name='Peanuts')
        self.dairy = Allergen.objects.create(name='Milk')

    def test_add_scanned_ingredients_requires_login(self):
        """Test that add scanned ingredients requires authentication."""
        self.client.logout()
        response = self.client.post(reverse('add-scanned-ingredients'))
        self.assertEqual(response.status_code, 302)

    def test_add_scanned_ingredients_success(self):
        """Test successfully adding scanned ingredients."""
        data = {
            'ingredients': [
                {
                    'name': 'Peanut Butter',
                    'brand': 'Jif',
                    'calories': 190,
                    'allergens': ['Peanuts']
                },
                {
                    'name': 'Milk',
                    'brand': 'Organic Valley',
                    'calories': 42,
                    'allergens': ['Milk']
                }
            ]
        }

        response = self.client.post(
            reverse('add-scanned-ingredients'),
            data=json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertEqual(response_data['added_count'], 2)

        self.assertTrue(Ingredient.objects.filter(name='Peanut Butter').exists())
        self.assertTrue(Ingredient.objects.filter(name='Milk').exists())

        pantry = Pantry.objects.get(user=self.user)
        self.assertEqual(pantry.ingredients.count(), 2)

    def test_add_scanned_ingredients_with_allergens(self):
        """Test that allergens are properly associated."""
        data = {
            'ingredients': [
                {
                    'name': 'Peanut Butter',
                    'brand': 'Generic',
                    'calories': 190,
                    'allergens': ['Peanuts']
                }
            ]
        }

        response = self.client.post(
            reverse('add-scanned-ingredients'),
            data=json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

        ingredient = Ingredient.objects.get(name='Peanut Butter')
        self.assertEqual(ingredient.allergens.count(), 1)
        self.assertIn(self.peanuts, ingredient.allergens.all())

    def test_add_scanned_ingredients_prevents_duplicates(self):
        """Test that duplicate ingredients aren't added twice."""
        data = {
            'ingredients': [
                {
                    'name': 'Banana',
                    'brand': 'Generic',
                    'calories': 89,
                    'allergens': []
                }
            ]
        }

        self.client.post(
            reverse('add-scanned-ingredients'),
            data=json.dumps(data),
            content_type='application/json'
        )

        pantry = Pantry.objects.get(user=self.user)
        count_after_first = pantry.ingredients.count()

        self.client.post(
            reverse('add-scanned-ingredients'),
            data=json.dumps(data),
            content_type='application/json'
        )

        pantry.refresh_from_db()
        count_after_second = pantry.ingredients.count()

        self.assertEqual(count_after_first, count_after_second)

    def test_add_scanned_ingredients_empty_list(self):
        """Test handling of empty ingredients list."""
        data = {'ingredients': []}

        response = self.client.post(
            reverse('add-scanned-ingredients'),
            data=json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])

    def test_add_scanned_ingredients_invalid_json(self):
        """Test handling of invalid JSON."""
        response = self.client.post(
            reverse('add-scanned-ingredients'),
            data='invalid json',
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])


class PantryScanIntegrationTest(TestCase):
    """Integration tests for complete pantry scan workflow."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

        Pantry.objects.create(user=self.user)

    @patch('services.scan_service.call_gpt_vision')
    @patch('services.scan_service.USDAIngredientValidator')
    def test_complete_scan_workflow(self, mock_validator_class, mock_gpt):
        """Test complete workflow from scan to add."""
        mock_gpt.return_value = ['Chicken Breast', 'Rice']

        mock_validator = MagicMock()
        mock_validator.validate_ingredients.return_value = [
            {
                'name': 'Chicken Breast',
                'brand': 'Generic',
                'calories': 165,
                'allergens': [],
                'validation_status': 'success'
            },
            {
                'name': 'Rice',
                'brand': 'Generic',
                'calories': 130,
                'allergens': [],
                'validation_status': 'success'
            }
        ]
        mock_validator_class.return_value = mock_validator

        image = BytesIO()
        test_image = Image.new('RGB', (100, 100))
        test_image.save(image, 'PNG')
        image.name = 'test.png'
        image.seek(0)

        scan_response = self.client.post(
            reverse('scan-pantry'),
            {'image': image}
        )

        self.assertEqual(scan_response.status_code, 200)
        scan_data = json.loads(scan_response.content)
        self.assertTrue(scan_data['success'])

        add_response = self.client.post(
            reverse('add-scanned-ingredients'),
            data=json.dumps({'ingredients': scan_data['detected_ingredients']}),
            content_type='application/json'
        )

        self.assertEqual(add_response.status_code, 200)
        add_data = json.loads(add_response.content)
        self.assertTrue(add_data['success'])
        self.assertEqual(add_data['added_count'], 2)

        pantry = Pantry.objects.get(user=self.user)
        self.assertEqual(pantry.ingredients.count(), 2)