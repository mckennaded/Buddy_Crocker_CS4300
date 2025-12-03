"""
Tests for USDA nutrition data functionality.

Tests the new nutrition_data, portion_data fields and related service functions.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
from buddy_crocker.models import Allergen, Ingredient, Pantry, Profile
from services import usda_api, usda_service
import json


class USDACompleteDataTest(TestCase):
    """Tests for get_complete_food_data function."""

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
                },
                {
                    'nutrient': {'id': 1004, 'name': 'Total lipid (fat)', 'unitName': 'g'},
                    'amount': 33
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
        self.assertEqual(result['basic']['brand'], 'Generic Brand')
        self.assertEqual(result['basic']['fdc_id'], 123456)
        self.assertEqual(result['basic']['calories_per_100g'], 403)

        # Check nutrients
        self.assertIn('macronutrients', result['nutrients'])
        self.assertIn('protein', result['nutrients']['macronutrients'])
        self.assertEqual(
            result['nutrients']['macronutrients']['protein']['amount'],
            25
        )

        # Check portions
        self.assertEqual(len(result['portions']), 1)
        self.assertEqual(result['portions'][0]['measure_unit'], 'cup, diced')
        self.assertEqual(result['portions'][0]['gram_weight'], 132)

        # Check ingredients text
        self.assertIn('milk', result['ingredients_text'])

    @patch('services.usda_api.get_food_details')
    def test_parse_nutrients_categorization(self, mock_get_details):
        """Test that nutrients are properly categorized."""
        mock_get_details.return_value = {
            'description': 'Test Food',
            'brandOwner': 'Generic',
            'dataType': 'Branded',
            'ingredients': '',
            'foodNutrients': [
                # Macronutrient
                {
                    'nutrient': {'id': 1003, 'name': 'Protein', 'unitName': 'g'},
                    'amount': 8
                },
                # Vitamin
                {
                    'nutrient': {'id': 1162, 'name': 'Vitamin C', 'unitName': 'mg'},
                    'amount': 60
                },
                # Mineral
                {
                    'nutrient': {'id': 1087, 'name': 'Calcium', 'unitName': 'mg'},
                    'amount': 300
                }
            ],
            'foodPortions': []
        }

        result = usda_api.get_complete_food_data(123456, use_cache=False)

        # Check categorization
        self.assertIn('protein', result['nutrients']['macronutrients'])
        self.assertIn('vitamin_c', result['nutrients']['vitamins'])
        self.assertIn('calcium', result['nutrients']['minerals'])

    @patch('services.usda_api.get_food_details')
    def test_parse_portions_multiple(self, mock_get_details):
        """Test parsing multiple portion sizes."""
        mock_get_details.return_value = {
            'description': 'Test Food',
            'brandOwner': 'Generic',
            'dataType': 'Branded',
            'ingredients': '',
            'foodNutrients': [],
            'foodPortions': [
                {
                    'id': 1,
                    'amount': 1,
                    'modifier': '',
                    'measureUnit': {'name': 'cup'},
                    'gramWeight': 240,
                    'portionDescription': '1 cup',
                    'sequenceNumber': 2
                },
                {
                    'id': 2,
                    'amount': 1,
                    'modifier': '',
                    'measureUnit': {'name': 'tablespoon'},
                    'gramWeight': 15,
                    'portionDescription': '1 tablespoon',
                    'sequenceNumber': 1
                }
            ]
        }

        result = usda_api.get_complete_food_data(123456, use_cache=False)

        # Should be sorted by sequence number
        self.assertEqual(len(result['portions']), 2)
        self.assertEqual(result['portions'][0]['measure_unit'], 'tablespoon')
        self.assertEqual(result['portions'][1]['measure_unit'], 'cup')


class IngredientNutritionFieldsTest(TestCase):
    """Tests for new Ingredient model fields and methods."""

    def setUp(self):
        """Set up test data."""
        self.allergen = Allergen.objects.create(
            name="Dairy",
            category="fda_major_9"
        )

    def test_ingredient_with_full_nutrition_data(self):
        """Test creating ingredient with complete nutrition data."""
        nutrition_data = {
            'macronutrients': {
                'protein': {'name': 'Protein', 'amount': 25, 'unit': 'g', 'nutrient_id': 1003},
                'total_fat': {'name': 'Fat', 'amount': 33, 'unit': 'g', 'nutrient_id': 1004}
            },
            'vitamins': {
                'vitamin_c': {'name': 'Vitamin C', 'amount': 0, 'unit': 'mg', 'nutrient_id': 1162}
            },
            'minerals': {},
            'other': {}
        }

        portion_data = [
            {
                'id': 1,
                'amount': 1,
                'modifier': '',
                'measure_unit': 'cup',
                'gram_weight': 132,
                'description': '1 cup, diced',
                'seq_num': 1
            }
        ]

        ingredient = Ingredient.objects.create(
            name='Cheddar Cheese',
            brand='Generic',
            calories=403,
            fdc_id=123456,
            nutrition_data=nutrition_data,
            portion_data=portion_data
        )

        # Test helper methods
        self.assertTrue(ingredient.has_nutrition_data())
        self.assertTrue(ingredient.has_portion_data())
        self.assertTrue(ingredient.is_usda_sourced())

        # Test get_nutrient method
        protein = ingredient.get_nutrient('protein', category='macronutrients')
        self.assertIsNotNone(protein)
        self.assertEqual(protein['amount'], 25)
        self.assertEqual(protein['unit'], 'g')

        # Test get_portion_by_unit method
        cup_portion = ingredient.get_portion_by_unit('cup')
        self.assertIsNotNone(cup_portion)
        self.assertEqual(cup_portion['gram_weight'], 132)

    def test_ingredient_without_nutrition_data(self):
        """Test ingredient without USDA nutrition data."""
        ingredient = Ingredient.objects.create(
            name='Homemade Item',
            brand='Generic',
            calories=100
        )

        self.assertFalse(ingredient.has_nutrition_data())
        self.assertFalse(ingredient.has_portion_data())
        self.assertFalse(ingredient.is_usda_sourced())
        self.assertIsNone(ingredient.fdc_id)

    def test_get_nutrient_nonexistent(self):
        """Test get_nutrient for non-existent nutrient."""
        ingredient = Ingredient.objects.create(
            name='Test',
            brand='Generic',
            calories=100,
            nutrition_data={
                'macronutrients': {},
                'vitamins': {},
                'minerals': {},
                'other': {}
            }
        )

        result = ingredient.get_nutrient('protein', category='macronutrients')
        self.assertIsNone(result)

    def test_get_portion_by_unit_case_insensitive(self):
        """Test get_portion_by_unit is case-insensitive."""
        portion_data = [
            {
                'measure_unit': 'Cup',
                'gram_weight': 240
            }
        ]

        ingredient = Ingredient.objects.create(
            name='Test',
            brand='Generic',
            calories=100,
            portion_data=portion_data
        )

        # Should find with lowercase
        result = ingredient.get_portion_by_unit('cup')
        self.assertIsNotNone(result)
        self.assertEqual(result['gram_weight'], 240)

        # Should find with uppercase
        result = ingredient.get_portion_by_unit('CUP')
        self.assertIsNotNone(result)


class AddIngredientWithUSDADataTest(TestCase):
    """Tests for add_ingredient view with USDA nutrition data."""

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

    @patch('buddy_crocker.views.get_complete_ingredient_data')
    def test_add_ingredient_fetches_usda_data(self, mock_get_data):
        """Test that adding ingredient with fdc_id fetches USDA data."""
        self.client.login(username='testuser', password='testpass123')

        mock_get_data.return_value = {
            'basic': {
                'name': 'Cheddar Cheese',
                'brand': 'Generic',
                'fdc_id': 123456,
                'data_type': 'Branded',
                'calories_per_100g': 403
            },
            'nutrients': {
                'macronutrients': {
                    'protein': {'name': 'Protein', 'amount': 25, 'unit': 'g', 'nutrient_id': 1003}
                },
                'vitamins': {},
                'minerals': {},
                'other': {}
            },
            'portions': [
                {
                    'measure_unit': 'cup',
                    'gram_weight': 132
                }
            ],
            'ingredients_text': 'milk, salt',
            'detected_allergens': []
        }

        response = self.client.post(
            reverse('add-ingredient'),
            {
                'name': 'Cheddar Cheese',
                'brand': 'Generic',
                'calories': 100,  # Will be overwritten
                'allergens': [],
                'fdc_id': '123456'
            }
        )

        self.assertEqual(response.status_code, 302)

        # Verify ingredient was created with USDA data
        ingredient = Ingredient.objects.get(name='Cheddar Cheese', brand='Generic')
        self.assertEqual(ingredient.calories, 403)  # Updated from USDA
        self.assertEqual(ingredient.fdc_id, 123456)
        self.assertTrue(ingredient.has_nutrition_data())
        self.assertTrue(ingredient.has_portion_data())

    @patch('buddy_crocker.views.get_complete_ingredient_data')
    def test_add_ingredient_usda_failure_continues(self, mock_get_data):
        """Test that ingredient is still saved when USDA fetch fails."""
        self.client.login(username='testuser', password='testpass123')

        # Simulate API failure
        mock_get_data.side_effect = Exception("API Error")

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

        # Should still succeed
        self.assertEqual(response.status_code, 302)

        # Ingredient should exist with form data
        ingredient = Ingredient.objects.get(name='Test Item')
        self.assertEqual(ingredient.calories, 100)
        # fdc_id is NOT saved when USDA fetch fails
        # The view only saves fdc_id inside the try block
        self.assertIsNone(ingredient.fdc_id)


class USDAServiceCalculationsTest(TestCase):
    """Tests for usda_service calculation functions."""

    def test_calculate_portion_calories(self):
        """Test calculating calories for specific portion."""
        calories_per_100g = 403
        gram_weight = 132  # 1 cup

        result = usda_service.calculate_portion_calories(
            calories_per_100g,
            gram_weight
        )

        expected = (403 * 132) / 100
        self.assertAlmostEqual(result, expected, places=1)

    def test_calculate_portion_calories_zero_values(self):
        """Test calculation with zero values."""
        result = usda_service.calculate_portion_calories(0, 100)
        self.assertEqual(result, 0)

        result = usda_service.calculate_portion_calories(100, 0)
        self.assertEqual(result, 0)

    def test_calculate_nutrient_for_portion(self):
        """Test calculating any nutrient for specific portion."""
        protein_per_100g = 25
        gram_weight = 132

        result = usda_service.calculate_nutrient_for_portion(
            protein_per_100g,
            gram_weight
        )

        expected = (25 * 132) / 100
        self.assertAlmostEqual(result, expected, places=2)

    def test_format_nutrient_display(self):
        """Test formatting nutrients for display."""
        nutrients = {
            'macronutrients': {
                'protein': {
                    'name': 'Protein',
                    'amount': 25.5,
                    'unit': 'g'
                }
            },
            'vitamins': {},
            'minerals': {},
            'other': {}
        }

        result = usda_service.format_nutrient_display(nutrients)

        self.assertIn('macronutrients', result)
        self.assertEqual(len(result['macronutrients']), 1)
        self.assertEqual(result['macronutrients'][0]['label'], 'Protein')
        self.assertEqual(result['macronutrients'][0]['value'], 25.5)
        self.assertEqual(result['macronutrients'][0]['formatted'], '25.5 g')


class USDAServiceAllergenDetectionTest(TestCase):
    """Tests for get_complete_ingredient_data with allergen detection."""

    def setUp(self):
        """Set up allergens."""
        self.dairy = Allergen.objects.create(
            name='Dairy',
            category='fda_major_9',
            alternative_names=['milk', 'cheese', 'lactose']
        )

    @patch('services.usda_api.get_complete_food_data')
    def test_allergen_detection_from_ingredients_text(self, mock_get_data):
        """Test that allergens are detected from ingredients text."""
        mock_get_data.return_value = {
            'basic': {
                'name': 'Cheddar Cheese',
                'brand': 'Generic',
                'fdc_id': 123456,
                'calories_per_100g': 403
            },
            'nutrients': {},
            'portions': [],
            'ingredients_text': 'Pasteurized milk, salt, enzymes'
        }

        result = usda_service.get_complete_ingredient_data(
            123456,
            Allergen.objects.all()
        )

        # Should detect Dairy from 'milk' in ingredients text
        self.assertGreater(len(result['detected_allergens']), 0)
        allergen_names = [a['name'] for a in result['detected_allergens']]
        self.assertIn('Dairy', allergen_names)


class ScanServiceUSDAIntegrationTest(TestCase):
    """Tests for scan_service integration with USDA nutrition data."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='scanuser',
            password='testpass123'
        )
        Profile.objects.filter(user=self.user).delete()

    @patch('services.scan_service.get_complete_ingredient_data')
    def test_add_scanned_ingredients_fetches_usda_data(self, mock_get_data):
        """Test that scanned ingredients fetch USDA nutrition data."""
        mock_get_data.return_value = {
            'basic': {
                'calories_per_100g': 250
            },
            'nutrients': {
                'macronutrients': {
                    'protein': {'name': 'Protein', 'amount': 8, 'unit': 'g'}
                },
                'vitamins': {},
                'minerals': {},
                'other': {}
            },
            'portions': [
                {'measure_unit': 'slice', 'gram_weight': 30}
            ],
            'ingredients_text': 'wheat flour, water'
        }

        from services.scan_service import add_ingredients_to_pantry

        ingredients_data = [
            {
                'name': 'Bread',
                'brand': 'Generic',
                'calories': 200,  # Will be updated
                'allergens': [],
                'fdc_id': 123456
            }
        ]

        result = add_ingredients_to_pantry(self.user, ingredients_data)

        self.assertTrue(result['success'])
        self.assertEqual(result['added_count'], 1)

        # Verify nutrition data was stored
        ingredient = Ingredient.objects.get(name='Bread')
        self.assertEqual(ingredient.calories, 250)  # Updated from USDA
        self.assertTrue(ingredient.has_nutrition_data())
        self.assertTrue(ingredient.has_portion_data())

    @patch('services.scan_service.get_complete_ingredient_data')
    def test_scan_continues_on_usda_failure(self, mock_get_data):
        """Test that scan continues even if USDA fetch fails."""
        # Simulate API failure
        mock_get_data.side_effect = Exception("API Error")

        from services.scan_service import add_ingredients_to_pantry

        ingredients_data = [
            {
                'name': 'Test Item',
                'brand': 'Generic',
                'calories': 100,
                'allergens': [],
                'fdc_id': 999999
            }
        ]

        result = add_ingredients_to_pantry(self.user, ingredients_data)

        # Should still succeed
        self.assertTrue(result['success'])
        self.assertEqual(result['added_count'], 1)

        # Ingredient should exist with form data
        ingredient = Ingredient.objects.get(name='Test Item')
        self.assertEqual(ingredient.calories, 100)


class IngredientDetailWithNutritionTest(TestCase):
    """Tests for ingredient detail view with nutrition data."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.nutrition_data = {
            'macronutrients': {
                'protein': {'name': 'Protein', 'amount': 25, 'unit': 'g'},
                'total_fat': {'name': 'Fat', 'amount': 33, 'unit': 'g'}
            },
            'vitamins': {
                'vitamin_c': {'name': 'Vitamin C', 'amount': 0, 'unit': 'mg'}
            },
            'minerals': {},
            'other': {}
        }

        self.portion_data = [
            {
                'measure_unit': 'cup',
                'gram_weight': 132,
                'description': '1 cup, diced'
            },
            {
                'measure_unit': 'slice',
                'gram_weight': 28,
                'description': '1 slice'
            }
        ]

        self.ingredient = Ingredient.objects.create(
            name='Cheddar Cheese',
            brand='Generic',
            calories=403,
            fdc_id=123456,
            nutrition_data=self.nutrition_data,
            portion_data=self.portion_data
        )

    def test_ingredient_detail_shows_nutrition_data(self):
        """Test that ingredient detail can access nutrition data."""
        response = self.client.get(
            reverse('ingredient-detail', args=[self.ingredient.pk])
        )

        self.assertEqual(response.status_code, 200)
        ingredient = response.context['ingredient']

        # Verify nutrition data is accessible
        self.assertTrue(ingredient.has_nutrition_data())
        protein = ingredient.get_nutrient('protein')
        self.assertEqual(protein['amount'], 25)

    def test_ingredient_detail_shows_portion_data(self):
        """Test that ingredient detail can access portion data."""
        response = self.client.get(
            reverse('ingredient-detail', args=[self.ingredient.pk])
        )

        self.assertEqual(response.status_code, 200)
        ingredient = response.context['ingredient']

        # Verify portion data is accessible
        self.assertTrue(ingredient.has_portion_data())
        self.assertEqual(len(ingredient.portion_data), 2)

        cup_portion = ingredient.get_portion_by_unit('cup')
        self.assertEqual(cup_portion['gram_weight'], 132)


class USDAAPIErrorHandlingTest(TestCase):
    """Tests for USDA API error handling."""

    @patch('services.usda_api.get_food_details')
    def test_get_complete_food_data_raises_on_error(self, mock_get_details):
        """Test that get_complete_food_data raises errors (no internal handling)."""
        mock_get_details.side_effect = usda_api.USDAAPIError("API Error")

        # get_complete_food_data doesn't catch exceptions
        with self.assertRaises(usda_api.USDAAPIError):
            usda_api.get_complete_food_data(123456, use_cache=False)

    @patch('services.usda_api.get_complete_food_data')
    def test_get_complete_ingredient_data_propagates_error(self, mock_get_complete_food_data):
        """Test that get_complete_ingredient_data propagates API errors to caller."""
        mock_get_complete_food_data.side_effect = usda_api.USDAAPIError("API Error")
        
        with self.assertRaises(usda_api.USDAAPIError):
            usda_service.get_complete_ingredient_data(123456)
