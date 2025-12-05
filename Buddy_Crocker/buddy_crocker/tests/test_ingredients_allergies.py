"""
Unit and integration tests for USDA ingredient search and allergen detection.

Tests the AJAX ingredient search endpoint, allergen detection logic,
and frontend integration.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
from buddy_crocker.models import Allergen, Ingredient, Pantry, Profile
from services import usda_api
from services.usda_service import detect_allergens_from_name, search_usda_foods
import json


class AllergenDetectionTest(TestCase):
    """Test cases for allergen detection from ingredient names."""

    def setUp(self):
        """Set up test allergens with alternative names."""
        self.peanuts = Allergen.objects.create(
            name="Peanuts",
            category="fda_major_9",
            alternative_names=["peanut", "groundnut", "arachis"]
        )
        self.dairy = Allergen.objects.create(
            name="Dairy",
            category="fda_major_9",
            alternative_names=[
                "milk", "lactose", "casein", "whey", "cream", "cheese"
            ]
        )
        self.gluten = Allergen.objects.create(
            name="Gluten",
            category="fda_major_9",
            alternative_names=["wheat", "barley", "rye"]
        )
        self.soy = Allergen.objects.create(
            name="Soy",
            category="fda_major_9",
            alternative_names=["soya", "soybean", "tofu"]
        )

    def test_detect_allergens_exact_match(self):
        """Test detection with exact allergen name match."""
        ingredient_name = "Peanuts Roasted"
        allergens = Allergen.objects.all()

        detected = detect_allergens_from_name(ingredient_name, allergens)

        self.assertEqual(len(detected), 1)
        self.assertIn(self.peanuts, detected)

    def test_detect_allergens_alternative_name_match(self):
        """Test detection using alternative names."""
        ingredient_name = "Whole Milk"
        allergens = Allergen.objects.all()

        detected = detect_allergens_from_name(ingredient_name, allergens)

        self.assertEqual(len(detected), 1)
        self.assertIn(self.dairy, detected)

    def test_detect_allergens_multiple_matches(self):
        """Test detection when ingredient contains multiple allergens."""
        ingredient_name = "Peanut Butter with Milk Chocolate"
        allergens = Allergen.objects.all()

        detected = detect_allergens_from_name(ingredient_name, allergens)

        self.assertEqual(len(detected), 2)
        self.assertIn(self.peanuts, detected)
        self.assertIn(self.dairy, detected)

    def test_detect_allergens_case_insensitive(self):
        """Test that detection is case-insensitive."""
        ingredient_name = "WHEAT BREAD"
        allergens = Allergen.objects.all()

        detected = detect_allergens_from_name(ingredient_name, allergens)

        self.assertEqual(len(detected), 1)
        self.assertIn(self.gluten, detected)

    def test_detect_allergens_no_match(self):
        """Test that no allergens are detected for safe ingredients."""
        ingredient_name = "Fresh Apple"
        allergens = Allergen.objects.all()

        detected = detect_allergens_from_name(ingredient_name, allergens)

        self.assertEqual(len(detected), 0)

    def test_detect_allergens_partial_word_match(self):
        """Test detection with partial word matches in compound words."""
        ingredient_name = "Soymilk"
        allergens = Allergen.objects.all()

        detected = detect_allergens_from_name(ingredient_name, allergens)

        self.assertGreaterEqual(len(detected), 1)
        self.assertIn(self.soy, detected)

    def test_detect_allergens_no_duplicates(self):
        """Test that the same allergen isn't added twice."""
        ingredient_name = "Peanut Butter with Peanuts"
        allergens = Allergen.objects.all()

        detected = detect_allergens_from_name(ingredient_name, allergens)

        peanut_count = sum(1 for a in detected if a.name == "Peanuts")
        self.assertEqual(peanut_count, 1)

    def test_detect_allergens_empty_string(self):
        """Test handling of empty ingredient name."""
        ingredient_name = ""
        allergens = Allergen.objects.all()

        detected = detect_allergens_from_name(ingredient_name, allergens)

        self.assertEqual(len(detected), 0)

    def test_detect_allergens_with_special_characters(self):
        """Test detection with special characters in ingredient name."""
        ingredient_name = "Cheese & Crackers (Wheat)"
        allergens = Allergen.objects.all()

        detected = detect_allergens_from_name(ingredient_name, allergens)

        self.assertGreaterEqual(len(detected), 1)


class USDASearchEndpointTest(TestCase):
    """Test cases for the USDA ingredient search AJAX endpoint."""

    def setUp(self):
        """Set up test client and allergens."""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123"
        )

        self.dairy = Allergen.objects.create(
            name="Dairy",
            category="fda_major_9",
            alternative_names=["milk", "cheese", "cheddar"]
        )
        self.gluten = Allergen.objects.create(
            name="Gluten",
            category="fda_major_9",
            alternative_names=["wheat", "bread"]
        )

    def test_search_endpoint_requires_query_parameter(self):
        """Test that endpoint returns empty results without query."""
        response = self.client.get(reverse('search-usda-ingredients'))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['results'], [])

    def test_search_endpoint_requires_minimum_query_length(self):
        """Test that short queries return empty results."""
        response = self.client.get(
            reverse('search-usda-ingredients'),
            {'q': 'a'}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['results'], [])

    @patch('services.usda_service.search_usda_foods')
    def test_search_endpoint_successful_search(self, mock_search):
        """Test successful USDA search returns formatted results."""
        mock_search.return_value = [
            {
                'name': 'Cheddar Cheese',
                'brand': 'Generic Brand',
                'calories': 403,
                'fdc_id': 123456,
                'data_type': 'Branded',
                'suggested_allergens': []
            }
        ]

        response = self.client.get(
            reverse('search-usda-ingredients'),
            {'q': 'cheddar'}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data['results']), 1)
        result = data['results'][0]

        self.assertEqual(result['name'], 'Cheddar Cheese')
        self.assertEqual(result['brand'], 'Generic Brand')
        self.assertEqual(result['calories'], 403)
        self.assertEqual(result['fdc_id'], 123456)

    @patch('services.usda_service.search_usda_foods')
    def test_search_endpoint_detects_allergens(self, mock_search):
        """Test that search results include detected allergens."""
        mock_search.return_value = [
            {
                'name': 'Cheddar Cheese',
                'brand': 'Generic',
                'calories': 403,
                'fdc_id': 123456,
                'data_type': 'Branded',
                'suggested_allergens': [
                    {'id': self.dairy.id, 'name': 'Dairy', 'category': 'fda_major_9'}
                ]
            }
        ]

        response = self.client.get(
            reverse('search-usda-ingredients'),
            {'q': 'cheddar'}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        result = data['results'][0]

        self.assertGreater(len(result['suggested_allergens']), 0)
        allergen_names = [a['name'] for a in result['suggested_allergens']]
        self.assertIn('Dairy', allergen_names)

    @patch('services.usda_service.search_usda_foods')
    def test_search_endpoint_error_handling(self, mock_search):
        """Test that API errors are handled gracefully."""
        mock_search.side_effect = usda_api.USDAAPIError("API Error")

        response = self.client.get(
            reverse('search-usda-ingredients'),
            {'q': 'test'}
        )

        self.assertEqual(response.status_code, 503)
        data = json.loads(response.content)
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'search_failed')

    @patch('services.usda_service.search_usda_foods')
    def test_search_endpoint_returns_multiple_results(self, mock_search):
        """Test that multiple search results are returned."""
        mock_search.return_value = [
            {
                'name': 'Sharp Cheddar',
                'brand': 'Brand A',
                'calories': 410,
                'fdc_id': 123456,
                'data_type': 'Branded',
                'suggested_allergens': []
            },
            {
                'name': 'Mild Cheddar',
                'brand': 'Brand B',
                'calories': 395,
                'fdc_id': 123457,
                'data_type': 'Branded',
                'suggested_allergens': []
            }
        ]

        response = self.client.get(
            reverse('search-usda-ingredients'),
            {'q': 'cheddar'}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data['results']), 2)

    @patch('services.usda_service.search_usda_foods')
    def test_search_endpoint_accessible_to_authenticated_users(self, mock_search):
        """Test that authenticated users can access the endpoint."""
        self.client.login(username="testuser", password="testpass123")

        mock_search.return_value = []
        response = self.client.get(
            reverse('search-usda-ingredients'),
            {'q': 'test'}
        )

        self.assertEqual(response.status_code, 200)

    @patch('services.usda_service.search_usda_foods')
    def test_search_endpoint_accessible_to_anonymous_users(self, mock_search):
        """Test that anonymous users can access the endpoint."""
        mock_search.return_value = []
        response = self.client.get(
            reverse('search-usda-ingredients'),
            {'q': 'test'}
        )

        self.assertEqual(response.status_code, 200)


class AddIngredientIntegrationTest(TestCase):
    """Integration tests for the add ingredient page with USDA search."""

    def setUp(self):
        """Set up test client and user."""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123"
        )
        Profile.objects.filter(user=self.user).delete()

        self.dairy = Allergen.objects.create(
            name="Dairy",
            category="fda_major_9",
            alternative_names=["milk", "cheese"]
        )

    def test_add_ingredient_page_loads_with_search_interface(self):
        """Test that the add ingredient page loads successfully."""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.get(reverse('add-ingredient'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'usda-search-input')
        self.assertContains(response, 'Search USDA Food Database')

    def test_add_ingredient_manual_entry_still_works(self):
        """Test that manual ingredient entry works alongside USDA search."""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.post(reverse('add-ingredient'), {
            'name': 'Custom Ingredient',
            'brand': 'Generic',
            'calories': 100,
            'allergens': []
        })

        self.assertEqual(response.status_code, 302)

        ingredient = Ingredient.objects.get(name='Custom Ingredient')
        self.assertEqual(ingredient.calories, 100)

    def test_add_ingredient_adds_to_pantry(self):
        """Test that new ingredients are added to user's pantry."""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.post(reverse('add-ingredient'), {
            'name': 'Test Ingredient',
            'brand': 'Generic',
            'calories': 50,
            'allergens': []
        })

        pantry = Pantry.objects.get(user=self.user)
        ingredient = Ingredient.objects.get(name='Test Ingredient')

        self.assertIn(ingredient, pantry.ingredients.all())


class BrandFieldTest(TestCase):
    """Test cases for the new brand field in Ingredient model."""

    def test_ingredient_brand_field_exists(self):
        """Test that brand field exists in Ingredient model."""
        ingredient = Ingredient.objects.create(
            name='Test',
            brand='Test Brand',
            calories=100
        )

        self.assertEqual(ingredient.brand, 'Test Brand')

    def test_ingredient_brand_default_value(self):
        """Test that brand defaults to Generic."""
        ingredient = Ingredient.objects.create(
            name='Test',
            calories=100
        )

        self.assertEqual(ingredient.brand, 'Generic')

    def test_ingredient_unique_together_name_brand(self):
        """Test that name+brand combination must be unique."""
        from django.db import IntegrityError

        Ingredient.objects.create(name='Cheese', brand='Brand A', calories=100)

        with self.assertRaises(IntegrityError):
            Ingredient.objects.create(
                name='Cheese',
                brand='Brand A',
                calories=105
            )

    def test_ingredient_same_name_different_brands_allowed(self):
        """Test that same name with different brands is allowed."""
        Ingredient.objects.create(name='Cheese', brand='Brand A', calories=100)
        Ingredient.objects.create(name='Cheese', brand='Brand B', calories=105)

        cheese_count = Ingredient.objects.filter(name='Cheese').count()
        self.assertEqual(cheese_count, 2)

    def test_ingredient_str_includes_brand(self):
        """Test that string representation includes brand for non-generic."""
        ingredient = Ingredient.objects.create(
            name='Peanut Butter',
            brand='Jif',
            calories=190
        )

        self.assertEqual(str(ingredient), 'Peanut Butter (Jif)')

    def test_ingredient_str_excludes_generic_brand(self):
        """Test that string representation excludes Generic brand."""
        ingredient = Ingredient.objects.create(
            name='Apple',
            brand='Generic',
            calories=95
        )

        self.assertEqual(str(ingredient), 'Apple')

    def test_ingredient_ordering_includes_brand(self):
        """Test that ingredients are ordered by name, then brand."""
        Ingredient.objects.create(name='Cheese', brand='Kraft', calories=100)
        Ingredient.objects.create(name='Cheese', brand='Generic', calories=95)
        Ingredient.objects.create(name='Apple', brand='Generic', calories=52)

        ingredients = list(Ingredient.objects.all())

        self.assertEqual(ingredients[0].name, 'Apple')
        self.assertEqual(ingredients[1].name, 'Cheese')
        self.assertEqual(ingredients[1].brand, 'Generic')
        self.assertEqual(ingredients[2].name, 'Cheese')
        self.assertEqual(ingredients[2].brand, 'Kraft')


class IngredientFormTest(TestCase):
    """Test cases for the IngredientForm with brand field."""

    def test_ingredient_form_includes_brand_field(self):
        """Test that form includes brand field."""
        from buddy_crocker.forms import IngredientForm

        form = IngredientForm()

        self.assertIn('brand', form.fields)

    def test_ingredient_form_brand_field_optional(self):
        """Test that brand field is optional."""
        from buddy_crocker.forms import IngredientForm

        form = IngredientForm()

        self.assertFalse(form.fields['brand'].required)

    def test_ingredient_form_brand_defaults_to_generic(self):
        """Test that brand field has Generic as initial value."""
        from buddy_crocker.forms import IngredientForm

        form = IngredientForm()

        self.assertEqual(form.fields['brand'].initial, 'Generic')

    def test_ingredient_form_validation_with_brand(self):
        """Test form validation with brand field."""
        from buddy_crocker.forms import IngredientForm

        form = IngredientForm(data={
            'name': 'Peanut Butter',
            'brand': 'Jif',
            'calories': 190,
            'allergens': []
        })

        self.assertTrue(form.is_valid())

    def test_ingredient_form_cleans_empty_brand_to_generic(self):
        """Test that empty brand is cleaned to Generic."""
        from buddy_crocker.forms import IngredientForm

        form = IngredientForm(data={
            'name': 'Apple',
            'brand': '',
            'calories': 95,
            'allergens': []
        })

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['brand'], 'Generic')