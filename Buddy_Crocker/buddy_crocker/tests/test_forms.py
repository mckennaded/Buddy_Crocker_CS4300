from django.contrib.auth.models import User
from django.test import TestCase
from django.forms import inlineformset_factory
from buddy_crocker.models import (
    Profile, Ingredient, Recipe, RecipeIngredient, Allergen
)
from buddy_crocker.forms import RecipeForm, RecipeIngredientForm, IngredientForm

class TestIngredientForm:
    def test_blank_name_is_invalid(self):
        form = IngredientForm(data={"name": ""})
        assert not form.is_valid()
        assert "name" in form.errors
        assert "Please enter an ingredient name." in form.errors["name"][0]

    def test_duplicate_name_is_invalid(self):
        Ingredient.objects.create(name="Cheddar")
        form = IngredientForm(data={"name": "cheddar"})
        assert not form.is_valid()
        assert "That ingredient already exists." in form.errors["name"][0]

    def test_valid_name(self):
        form = IngredientForm(data={"name": "Green Onion"})
        assert form.is_valid()
        ing = form.save()
        assert ing.pk

class RecipeFormTest(TestCase):
    """Test cases for RecipeForm and RecipeIngredientFormSet."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        Profile.objects.filter(user=self.user).delete()

        self.pantry = Pantry.objects.create(user=self.user)
        self.ingredient = Ingredient.objects.create(
            name='Test Ingredient',
            calories=100
        )
        self.pantry.ingredients.add(self.ingredient)

    def test_recipe_form_valid_data(self):
        """Test recipe form with valid data."""
        from buddy_crocker.forms import RecipeForm

        form_data = {
            'title': 'Test Recipe',
            'instructions': 'Test instructions',
            'servings': 4,
            'prep_time': 15,
            'cook_time': 30,
            'difficulty': 'medium'
        }

        form = RecipeForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_recipe_form_missing_required_fields(self):
        """Test recipe form with missing required fields."""
        from buddy_crocker.forms import RecipeForm

        form_data = {
            'title': '',  # Required
            'instructions': '',  # Required
            'servings': 4
        }

        form = RecipeForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
        self.assertIn('instructions', form.errors)

    def test_recipe_form_optional_fields(self):
        """Test that time fields are optional."""
        from buddy_crocker.forms import RecipeForm

        form_data = {
            'title': 'Simple Recipe',
            'instructions': 'Easy steps',
            'servings': 2,
            'difficulty': 'easy'
            # No prep_time or cook_time
        }

        form = RecipeForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_recipe_ingredient_form_valid(self):
        """Test recipe ingredient form with valid data."""
        from buddy_crocker.forms import RecipeIngredientForm

        form_data = {
            'ingredient': self.ingredient.pk,
            'amount': '2.0',
            'unit': 'cup',
            'notes': 'chopped'
        }

        form = RecipeIngredientForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_recipe_ingredient_form_missing_required(self):
        """Test recipe ingredient form with missing required fields."""
        from buddy_crocker.forms import RecipeIngredientForm

        form_data = {
            'ingredient': self.ingredient.pk,
            # Missing amount and unit
        }

        form = RecipeIngredientForm(data=form_data)
        self.assertFalse(form.is_valid())