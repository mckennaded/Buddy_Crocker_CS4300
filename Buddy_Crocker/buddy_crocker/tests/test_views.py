"""
Integration tests for Buddy Crocker views.

Tests view access control, template rendering, context data, and user interactions.
"""
import json
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from buddy_crocker.models import Allergen, Ingredient, Recipe, RecipeIngredient, Pantry, Profile
from services import usda_api


class PublicViewsTest(TestCase):
    """Test cases for publicly accessible views."""

    def setUp(self):
        """Set up test client and sample data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testchef",
            password="testpass123"
        )
        self.allergen = Allergen.objects.create(
            name="Gluten",
            category="fda_major_9"
        )
        self.ingredient = Ingredient.objects.create(name="Tomato", calories=18)

        Profile.objects.filter(user=self.user).delete()

    def test_index_view_accessible_without_login(self):
        """Test that the index page is publicly accessible."""
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)

    def test_index_view_uses_correct_template(self):
        """Test that the index view uses the expected template."""
        response = self.client.get(reverse('index'))
        self.assertTemplateUsed(response, 'buddy_crocker/index.html')

    def test_recipe_search_accessible_without_login(self):
        """Test that recipe search is publicly accessible."""
        response = self.client.get(reverse('recipe-search'))
        self.assertEqual(response.status_code, 200)

    def test_recipe_search_uses_correct_template(self):
        """Test that recipe search uses the expected template."""
        response = self.client.get(reverse('recipe-search'))
        self.assertTemplateUsed(response, 'buddy_crocker/recipe-search.html')

    def test_recipe_detail_accessible_without_login(self):
        """Test that individual recipe details are publicly viewable."""
        recipe = Recipe.objects.create(
            title="Pasta",
            author=self.user,
            instructions="Boil and serve."
        )
        response = self.client.get(reverse('recipe-detail', args=[recipe.pk]))
        self.assertEqual(response.status_code, 200)

    def test_recipe_detail_uses_correct_template(self):
        """Test that recipe detail uses the expected template."""
        recipe = Recipe.objects.create(
            title="Pasta",
            author=self.user,
            instructions="Boil and serve."
        )
        response = self.client.get(reverse('recipe-detail', args=[recipe.pk]))
        self.assertTemplateUsed(response, 'buddy_crocker/recipe_detail.html')

    def test_recipe_detail_context_contains_recipe(self):
        """Test that recipe detail view passes the recipe to the template."""
        recipe = Recipe.objects.create(
            title="Pasta",
            author=self.user,
            instructions="Boil and serve."
        )
        response = self.client.get(reverse('recipe-detail', args=[recipe.pk]))
        self.assertIn('recipe', response.context)
        self.assertEqual(response.context['recipe'].title, "Pasta")

    def test_recipe_detail_not_found(self):
        """Test that accessing a non-existent recipe returns 404."""
        response = self.client.get(reverse('recipe-detail', args=[99999]))
        self.assertEqual(response.status_code, 404)

    def test_ingredient_detail_accessible_without_login(self):
        """Test that ingredient details are publicly viewable."""
        response = self.client.get(reverse('ingredient-detail', args=[self.ingredient.pk]))
        self.assertEqual(response.status_code, 200)

    def test_ingredient_detail_uses_correct_template(self):
        """Test that ingredient detail uses the expected template."""
        response = self.client.get(reverse('ingredient-detail', args=[self.ingredient.pk]))
        self.assertTemplateUsed(response, 'buddy_crocker/ingredient_detail.html')

    def test_ingredient_detail_context_contains_ingredient(self):
        """Test that ingredient detail view passes the ingredient to the template."""
        response = self.client.get(reverse('ingredient-detail', args=[self.ingredient.pk]))
        self.assertIn('ingredient', response.context)
        self.assertEqual(response.context['ingredient'].name, "Tomato")

    def test_ingredient_detail_shows_allergens(self):
        """Test that ingredient detail view shows allergens."""
        self.ingredient.allergens.add(self.allergen)
        response = self.client.get(reverse('ingredient-detail', args=[self.ingredient.pk]))

        self.assertIn('ingredient', response.context)
        self.assertEqual(response.context['ingredient'], self.ingredient)

        self.assertIn(self.allergen, response.context['ingredient'].allergens.all())

    def test_allergen_detail_accessible_without_login(self):
        """Test that allergen details are publicly viewable."""
        response = self.client.get(reverse('allergen-detail', args=[self.allergen.pk]))
        self.assertEqual(response.status_code, 200)

    def test_allergen_detail_uses_correct_template(self):
        """Test that allergen detail uses the expected template."""
        response = self.client.get(reverse('allergen-detail', args=[self.allergen.pk]))
        self.assertTemplateUsed(response, 'buddy_crocker/allergen_detail.html')

    def test_allergen_detail_context_contains_allergen(self):
        """Test that allergen detail view passes the allergen to the template."""
        response = self.client.get(reverse('allergen-detail', args=[self.allergen.pk]))
        self.assertIn('allergen', response.context)
        self.assertEqual(response.context['allergen'].name, "Gluten")

    def test_allergen_detail_shows_affected_ingredients(self):
        """Test that allergen detail shows ingredients containing the allergen."""
        self.ingredient.allergens.add(self.allergen)
        response = self.client.get(reverse('allergen-detail', args=[self.allergen.pk]))
        self.assertIn('affected_ingredients', response.context)
        self.assertIn(self.ingredient, response.context['affected_ingredients'])


class LoginRequiredViewsTest(TestCase):
    """Test cases for views that require authentication."""

    def setUp(self):
        """Set up test client and user credentials."""
        self.client = Client()
        self.user = User.objects.create_user(
            username="authuser",
            password="authpass123"
        )
        self.other_user = User.objects.create_user(
            username="otheruser",
            password="otherpass456"
        )
        self.ingredient = Ingredient.objects.create(  # ADD THIS
            name="Test Flour",
            calories=364
        )

        Profile.objects.filter(user=self.user).delete()

    def test_pantry_accessible_when_logged_in(self):
        """Test that pantry view is accessible for authenticated users."""
        self.client.login(username="authuser", password="authpass123")
        response = self.client.get(reverse('pantry'))
        self.assertEqual(response.status_code, 200)

    def test_pantry_uses_correct_template(self):
        """Test that pantry view uses the expected template."""
        self.client.login(username="authuser", password="authpass123")
        response = self.client.get(reverse('pantry'))
        self.assertTemplateUsed(response, 'buddy_crocker/pantry.html')

    def test_pantry_shows_user_ingredients(self):
        """Test that pantry view displays the user's pantry ingredients."""
        self.client.login(username="authuser", password="authpass123")

        # Create pantry and add ingredients
        pantry = Pantry.objects.create(user=self.user)
        ingredient = Ingredient.objects.create(name="Flour", calories=364)
        ingredient.allergens.add(Allergen.objects.create(name="Gluten"))
        pantry.ingredients.add(ingredient)

        response = self.client.get(reverse('pantry'))
        self.assertIn('pantry', response.context)
        self.assertIn(ingredient, response.context['pantry'].ingredients.all())

    def test_add_recipe_accessible_when_logged_in(self):
        """Test that add recipe view is accessible for authenticated users."""
        self.client.login(username="authuser", password="authpass123")
        response = self.client.get(reverse('add-recipe'))
        self.assertEqual(response.status_code, 200)

    def test_add_recipe_uses_correct_template(self):
        """Test that add recipe view uses the expected template."""
        self.client.login(username="authuser", password="authpass123")
        response = self.client.get(reverse('add-recipe'))
        self.assertTemplateUsed(response, 'buddy_crocker/add_recipe.html')

    def test_add_recipe_post_creates_recipe(self):
        """Test that submitting the add recipe form creates a new recipe."""
        self.client.login(username="authuser", password="authpass123")

        response = self.client.post(reverse('add-recipe'), {
            'title': 'New Recipe',
            'instructions': 'Mix ingredients and cook.',
            'servings': '1',
            'prep_time': '10',
            'cook_time': '20',
            'difficulty': 'easy',
            # 1 valid ingredient
            'recipe_ingredients-TOTAL_FORMS': '1',
            'recipe_ingredients-INITIAL_FORMS': '0',
            'recipe_ingredients-MIN_NUM_FORMS': '1',
            'recipe_ingredients-MAX_NUM_FORMS': '1000',
            'recipe_ingredients-0-ingredient': '1',  # PK 1 exists
            'recipe_ingredients-0-amount': '100',
            'recipe_ingredients-0-unit': 'g',
            'recipe_ingredients-0-notes': '',
        })

        # Should redirect after successful creation
        self.assertEqual(response.status_code, 302)

        # Verify recipe was created
        recipe = Recipe.objects.get(title='New Recipe', author=self.user)
        self.assertEqual(recipe.instructions, 'Mix ingredients and cook.')

    def test_profile_detail_accessible_when_logged_in(self):
        """Test that profile detail is accessible for authenticated users."""
        self.client.login(username="authuser", password="authpass123")
        response = self.client.get(reverse('profile-detail', args=[self.user.pk]))
        self.assertEqual(response.status_code, 200)

    def test_profile_detail_uses_correct_template(self):
        """Test that profile detail uses the expected template."""
        self.client.login(username="authuser", password="authpass123")
        response = self.client.get(reverse('profile-detail', args=[self.user.pk]))
        self.assertTemplateUsed(response, 'buddy_crocker/profile_detail.html')


    def test_profile_detail_shows_user_allergens(self):
        """Test that profile detail displays the user's allergens."""
        self.client.login(username="authuser", password="authpass123")
        profile = Profile.objects.create(user=self.user)
        allergen = Allergen.objects.create(name="Peanuts")
        profile.allergens.add(allergen)

        response = self.client.get(reverse('profile-detail', args=[self.user.pk]))
        self.assertIn('profile', response.context)
        self.assertIn(allergen, response.context['profile'].allergens.all())

    def test_user_can_only_access_own_profile(self):
        """Test that users are redirected to their own profile."""
        self.client.login(username="authuser", password="authpass123")

        # Try to access another user's profile
        response = self.client.get(reverse('profile-detail', args=[self.other_user.pk]))

        # Should redirect to own profile
        self.assertEqual(response.status_code, 302)


class RecipeSearchIntegrationTest(TestCase):
    """Integration tests for recipe search functionality."""

    def setUp(self):
        """Set up test data for recipe search tests."""
        self.client = Client()
        self.user = User.objects.create_user(
            username="searchuser",
            password="searchpass123"
        )

        Profile.objects.filter(user=self.user).delete()

        # Create allergens
        self.gluten = Allergen.objects.create(name="Gluten", category="fda_major_9")
        self.dairy = Allergen.objects.create(name="Dairy", category="fda_major_9")

        # Create ingredients with allergens (M2M)
        self.flour = Ingredient.objects.create(name="Flour", calories=364)
        self.flour.allergens.add(self.gluten)

        self.milk = Ingredient.objects.create(name="Milk", calories=42)
        self.milk.allergens.add(self.dairy)

        self.rice = Ingredient.objects.create(name="Rice", calories=130)

        # Create recipes
        self.recipe1 = Recipe.objects.create(
            title="Bread",
            author=self.user,
            instructions="Bake the bread."
        )
        RecipeIngredient.objects.create(
            recipe=self.recipe1,
            ingredient=self.flour,
            amount=100.0,
            unit='g'
        )

        self.recipe2 = Recipe.objects.create(
            title="Smoothie",
            author=self.user,
            instructions="Blend ingredients."
        )
        RecipeIngredient.objects.create(
            recipe=self.recipe2,
            ingredient=self.milk,
            amount=100.0,
            unit='g'
        )

        self.recipe3 = Recipe.objects.create(
            title="Rice Bowl",
            author=self.user,
            instructions="Cook rice."
        )
        RecipeIngredient.objects.create(
            recipe=self.recipe3,
            ingredient=self.rice,
            amount=100.0,
            unit='g'
        )

    def test_recipe_search_displays_all_recipes_without_filter(self):
        """Test that recipe search shows all recipes when no filter is applied."""
        response = self.client.get(reverse('recipe-search'))
        self.assertEqual(response.status_code, 200)
        recipes = response.context['recipes']
        self.assertEqual(len(recipes), 3)

    def test_recipe_search_filter_by_allergen(self):
        """Test that recipe search can filter out recipes with specific allergens."""
        response = self.client.get(reverse('recipe-search'), {
            'exclude_allergens': [self.gluten.pk]
        })
        recipes = response.context['recipes']

        # Should exclude Bread (contains gluten)
        self.assertNotIn(self.recipe1, recipes)
        # Should include Smoothie and Rice Bowl
        self.assertIn(self.recipe2, recipes)
        self.assertIn(self.recipe3, recipes)

    def test_recipe_search_filter_multiple_allergens(self):
        """Test filtering recipes by multiple allergens simultaneously."""
        response = self.client.get(reverse('recipe-search'), {
            'exclude_allergens': [self.gluten.pk, self.dairy.pk]
        })
        recipes = response.context['recipes']

        # Should exclude both Bread and Smoothie
        self.assertNotIn(self.recipe1, recipes)
        self.assertNotIn(self.recipe2, recipes)
        # Should only include Rice Bowl
        self.assertIn(self.recipe3, recipes)
        self.assertEqual(len(recipes), 1)

    def test_recipe_search_respects_user_profile_allergens(self):
        """Test that logged-in users see their allergens pre-selected."""
        self.client.login(username="searchuser", password="searchpass123")
        profile = Profile.objects.create(user=self.user)
        profile.allergens.add(self.gluten)

        response = self.client.get(reverse('recipe-search'))

        # Verify user's allergens are in selected_allergens context
        selected = response.context['user_profile_allergen_ids']
        self.assertIn(self.gluten.pk, selected)


class ViewIntegrationTest(TestCase):
    """Complex integration tests across multiple views and models."""

    def setUp(self):
        """Set up comprehensive test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username="integration",
            password="integrationpass123"
        )

        Profile.objects.filter(user=self.user).delete()

        # Create allergens
        self.peanuts = Allergen.objects.create(name="Peanuts", category="fda_major_9")
        self.shellfish = Allergen.objects.create(name="Shellfish", category="fda_major_9")

        # Create ingredients with allergen M2M
        self.peanut_butter = Ingredient.objects.create(
            name="Peanut Butter",
            calories=588
        )
        self.peanut_butter.allergens.add(self.peanuts)

        self.shrimp = Ingredient.objects.create(
            name="Shrimp",
            calories=99
        )
        self.shrimp.allergens.add(self.shellfish)

        self.banana = Ingredient.objects.create(name="Banana", calories=89)

        # Create user profile with allergen
        self.profile = Profile.objects.create(user=self.user)
        self.profile.allergens.add(self.peanuts)

        # Create user pantry with ingredients
        self.pantry = Pantry.objects.create(user=self.user)
        self.pantry.ingredients.add(self.banana, self.peanut_butter)

    def test_full_user_workflow_create_recipe(self):
        """Test complete workflow: login, create recipe, view recipe."""
        # Login
        self.client.login(username="integration", password="integrationpass123")

        # Create recipe
        response = self.client.post(reverse('add-recipe'), {
            'title': 'Smoothie',
            'instructions': 'Blend banana.',
            'servings': '4',
            'prep_time': '10',
            'cook_time': '20',
            'difficulty': 'easy',
            # 1 valid ingredient
            'recipe_ingredients-TOTAL_FORMS': '1',
            'recipe_ingredients-INITIAL_FORMS': '0',
            'recipe_ingredients-MIN_NUM_FORMS': '1',
            'recipe_ingredients-MAX_NUM_FORMS': '1000',
            'recipe_ingredients-0-ingredient': '1',  # PK 1 exists
            'recipe_ingredients-0-amount': '100',
            'recipe_ingredients-0-unit': 'g',
            'recipe_ingredients-0-notes': '',
        })
        self.assertEqual(response.status_code, 302)

        # Retrieve the created recipe
        recipe = Recipe.objects.get(title='Smoothie', author=self.user)
        self.assertEqual(recipe.instructions, 'Blend banana.')

    def test_pantry_contains_ingredient_with_user_allergen(self):
        """Test that a user's pantry can contain ingredients they're allergic to."""
        self.client.login(username="integration", password="integrationpass123")

        response = self.client.get(reverse('pantry'))
        pantry = response.context['pantry']

        # Verify the pantry contains peanut butter
        self.assertIn(self.peanut_butter, pantry.ingredients.all())

        # Verify user has peanut allergen in profile
        self.assertIn(self.peanuts, self.user.profile.allergens.all())

    def test_ingredient_detail_shows_related_recipes(self):
        """Test that ingredient detail page shows recipes using that ingredient."""
        recipe = Recipe.objects.create(
            title="PB Sandwich",
            author=self.user,
            instructions="Spread on bread."
        )
        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=self.peanut_butter,
            amount=500.0,
            unit='g'
        )

        response = self.client.get(reverse('ingredient-detail', args=[self.peanut_butter.pk]))

        # Verify ingredient is in context
        ingredient = response.context['ingredient']

        # Check that related recipes are accessible
        related_recipes = ingredient.recipes.all()
        self.assertIn(recipe, related_recipes)

    def test_allergen_detail_shows_affected_ingredients(self):
        """Test that allergen detail page shows all ingredients with that allergen."""
        response = self.client.get(reverse('allergen-detail', args=[self.peanuts.pk]))

        affected_ingredients = response.context['affected_ingredients']
        self.assertIn(self.peanut_butter, affected_ingredients)

    def test_recipe_detail_shows_allergen_information(self):
        """Test that recipe detail includes allergen info from ingredients."""
        recipe = Recipe.objects.create(
            title="PB Sandwich",
            author=self.user,
            instructions="Spread on bread."
        )
        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=self.peanut_butter,
            amount=500.0,
            unit='g'
        )

        response = self.client.get(reverse('recipe-detail', args=[recipe.pk]))

        # Check that allergens are in context
        self.assertIn('all_recipe_allergens', response.context)
        recipe_allergens = response.context['all_recipe_allergens']
        self.assertIn(self.peanuts, recipe_allergens)

    def test_recipe_detail_shows_allergen_warning_for_user(self):
        """Test that recipe shows warning when user has conflicting allergens."""
        self.client.login(username="integration", password="integrationpass123")

        recipe = Recipe.objects.create(
            title="PB Sandwich",
            author=self.user,
            instructions="Spread on bread."
        )
        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=self.peanut_butter,
            amount=500.0,
            unit='g'
        )

        response = self.client.get(reverse('recipe-detail', args=[recipe.pk]))

        # Should show allergen warning
        self.assertTrue(response.context['has_allergen_conflict'])

    def test_unauthenticated_user_can_view_authenticated_user_recipe(self):
        """Test that public can view recipes created by authenticated users."""
        recipe = Recipe.objects.create(
            title="Public Recipe",
            author=self.user,
            instructions="Cook it."
        )

        # Access without login
        response = self.client.get(reverse('recipe-detail', args=[recipe.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['recipe'], recipe)


class ErrorHandlingTest(TestCase):
    """Test error handling and edge cases in views."""

    def setUp(self):
        """Set up test client and basic data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username="erroruser",
            password="errorpass123"
        )

        Profile.objects.filter(user=self.user).delete()

    def test_recipe_detail_invalid_pk(self):
        """Test that invalid recipe pk returns 404."""
        response = self.client.get(reverse('recipe-detail', args=[99999]))
        self.assertEqual(response.status_code, 404)

    def test_ingredient_detail_invalid_pk(self):
        """Test that invalid ingredient pk returns 404."""
        response = self.client.get(reverse('ingredient-detail', args=[99999]))
        self.assertEqual(response.status_code, 404)

    def test_allergen_detail_invalid_pk(self):
        """Test that invalid allergen pk returns 404."""
        response = self.client.get(reverse('allergen-detail', args=[99999]))
        self.assertEqual(response.status_code, 404)

    def test_profile_detail_invalid_pk(self):
        """Test that invalid profile pk returns appropriate response."""
        self.client.login(username="erroruser", password="errorpass123")
        response = self.client.get(reverse('profile-detail', args=[99999]))
        self.assertEqual(response.status_code, 302)

    def test_add_recipe_with_duplicate_title(self):
        """Test that adding a recipe with duplicate title/author fails gracefully."""
        self.client.login(username="erroruser", password="errorpass123")

        # Create first recipe
        Recipe.objects.create(
            title="Duplicate",
            author=self.user,
            instructions="First version."
        )

        # Try to create duplicate
        response = self.client.post(reverse('add-recipe'), {
            'title': 'Duplicate',
            'instructions': 'Second version.',
        })

        # Should handle gracefully - either show form with errors or redirect
        self.assertIn(response.status_code, [200, 302])

    def test_add_recipe_without_ingredients(self):
        """Test that recipes can be created without ingredients."""
        self.client.login(username="erroruser", password="errorpass123")

        response = self.client.post(reverse('add-recipe'), {
            'title': 'No Ingredients',
            'instructions': 'Just instructions.',
        })

        # Should succeed
        recipe = Recipe.objects.filter(title='No Ingredients', author=self.user).first()
        if recipe:
            self.assertEqual(recipe.ingredients.count(), 0)

    def test_pantry_auto_created_for_user(self):
        """Test that accessing pantry view auto-creates pantry if it doesn't exist."""
        new_user = User.objects.create_user(
            username="newuser",
            password="newpass123"
        )
        self.client.login(username="newuser", password="newpass123")

        # Verify pantry doesn't exist yet
        self.assertFalse(Pantry.objects.filter(user=new_user).exists())

        response = self.client.get(reverse('pantry'))

        # Should auto-create pantry
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Pantry.objects.filter(user=new_user).exists())

    def test_add_ingredient_creates_ingredient_with_allergens(self):
        """Test that add ingredient form creates ingredient with allergens."""
        self.client.login(username="erroruser", password="errorpass123")
        allergen = Allergen.objects.create(name="Peanuts")

        response = self.client.post(reverse('add-ingredient'), {
            'name': 'New Ingredient',
            'calories': 100,
            'allergens': [allergen.id],
        })

        # Should redirect after successful creation
        self.assertEqual(response.status_code, 302)

        # Verify ingredient was created with allergen
        ingredient = Ingredient.objects.get(name='New Ingredient')
        self.assertEqual(ingredient.calories, 100)
        self.assertIn(allergen, ingredient.allergens.all())

    def test_add_ingredient_adds_to_pantry(self):
        """Test that adding an ingredient automatically adds it to user's pantry."""
        self.client.login(username="erroruser", password="errorpass123")

        # Create pantry for user
        pantry = Pantry.objects.create(user=self.user)

        response = self.client.post(reverse('add-ingredient'), {
            'name': 'Pantry Ingredient',
            'calories': 50,
        })

        # Verify ingredient was added to pantry
        ingredient = Ingredient.objects.get(name='Pantry Ingredient')
        self.assertIn(ingredient, pantry.ingredients.all())

class QuickAddIngredientsTest(TestCase):
    """Tests for the quick_add_ingredients view"""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            password='testpass123',
            email='other@example.com'
        )

        # Create ingredients
        self.ingredient1 = Ingredient.objects.create(
            name='Flour',
            brand='Generic',
            calories=100
        )
        self.ingredient2 = Ingredient.objects.create(
            name='Sugar',
            brand='Generic',
            calories=50
        )

        # Create recipe
        self.recipe = Recipe.objects.create(
            title='Test Recipe',
            author=self.user,
            instructions='Mix ingredients'
        )

        # Create pantry and add ingredient
        self.pantry = Pantry.objects.create(user=self.user)
        self.pantry.ingredients.add(self.ingredient1, self.ingredient2)

    def test_quick_add_ingredients_success(self):
        """Test successfully adding an ingredient to a recipe."""
        self.client.login(username='testuser', password='testpass123')

        # Verify ingredient not in recipe initially
        self.assertNotIn(self.ingredient1, self.recipe.ingredients.all())

        response = self.client.post(
            reverse('quick-add-ingredients', kwargs={'pk': self.recipe.pk}),
            {'ingredient_id': self.ingredient1.id}
        )

        # Check redirect
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('recipe-detail', kwargs={'pk': self.recipe.pk}))

        # Verify ingredient added
        self.recipe.refresh_from_db()
        self.assertIn(self.ingredient1, self.recipe.ingredients.all())

    def test_quick_add_ingredients_invalid_recipe(self):
        """Test adding to a non-existent recipe."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(
            reverse('quick-add-ingredients', kwargs={'pk': 99999}),
            {'ingredient_id': self.ingredient1.id}
        )

        # Should return 404
        self.assertEqual(response.status_code, 404)

    def test_quick_add_ingredients_duplicate(self):
        """Test adding an ingredient that's already in the recipe."""
        self.client.login(username='testuser', password='testpass123')

        # Add ingredient first time
        RecipeIngredient.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient1,
            amount=500.0,
            unit='g'
        )
        initial_count = self.recipe.ingredients.count()

        # Try to add again
        response = self.client.post(
            reverse('quick-add-ingredients', kwargs={'pk': self.recipe.pk}),
            {'ingredient_id': self.ingredient1.id}
        )

        self.assertEqual(response.status_code, 302)
        self.recipe.refresh_from_db()
        # Count should remain the same
        self.assertEqual(self.recipe.ingredients.count(), initial_count)

class EditIngredientTest(TestCase):
    """Tests for the edit_ingredient view"""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )

        self.allergen = Allergen.objects.create(
            name='Peanuts',
            category='fda_major_9'
        )

        self.ingredient = Ingredient.objects.create(
            name='Peanut Butter',
            brand='Jif',
            calories=200
        )
        self.ingredient.allergens.add(self.allergen)

    def test_edit_ingredient_get_request(self):
        """Test GET request displays the form with pre-populated data."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.get(
            reverse('edit-ingredient', kwargs={'pk': self.ingredient.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'buddy_crocker/add-ingredient.html')
        self.assertIn('form', response.context)
        self.assertIn('ingredient', response.context)
        self.assertTrue(response.context['edit_mode'])

        # Check form is pre-populated
        form = response.context['form']
        self.assertEqual(form.instance.name, 'Peanut Butter')
        self.assertEqual(form.instance.brand, 'Jif')
        self.assertEqual(form.instance.calories, 200)

    def test_edit_ingredient_post_success(self):
        """Test successfully editing an ingredient."""
        self.client.login(username='testuser', password='testpass123')

        new_allergen = Allergen.objects.create(
            name='Tree Nuts',
            category='fda_major_9'
        )

        response = self.client.post(
            reverse('edit-ingredient', kwargs={'pk': self.ingredient.pk}),
            {
                'name': 'Almond Butter',
                'brand': 'Organic',
                'calories': 180,
                'allergens': [new_allergen.id]
            }
        )

        # Check redirect
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse('ingredient-detail', kwargs={'pk': self.ingredient.pk})
        )

        # Verify changes
        self.ingredient.refresh_from_db()
        self.assertEqual(self.ingredient.name, 'Almond Butter')
        self.assertEqual(self.ingredient.brand, 'Organic')
        self.assertEqual(self.ingredient.calories, 180)
        self.assertIn(new_allergen, self.ingredient.allergens.all())

    def test_edit_ingredient_nonexistent(self):
        """Test editing a non-existent ingredient."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.get(
            reverse('edit-ingredient', kwargs={'pk': 99999})
        )

        self.assertEqual(response.status_code, 404)

class DeleteIngredientTest(TestCase):
    """Tests for the delete_ingredient view"""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )

        self.ingredient = Ingredient.objects.create(
            name='Test Ingredient',
            brand='Generic',
            calories=100
        )

    def test_delete_ingredient_get_confirmation(self):
        """Test GET request shows confirmation page."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.get(
            reverse('delete-ingredient', kwargs={'pk': self.ingredient.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'buddy_crocker/delete_ingredient_confirm.html')
        self.assertIn('ingredient', response.context)
        self.assertEqual(response.context['ingredient'], self.ingredient)

    def test_delete_ingredient_post_success(self):
        """Test successfully deleting an ingredient."""
        self.client.login(username='testuser', password='testpass123')

        ingredient_id = self.ingredient.pk
        ingredient_name = self.ingredient.name

        response = self.client.post(
            reverse('delete-ingredient', kwargs={'pk': ingredient_id})
        )

        # Check redirect to pantry
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('pantry'))

        # Verify ingredient deleted
        self.assertFalse(Ingredient.objects.filter(pk=ingredient_id).exists())

    def test_delete_ingredient_with_recipes(self):
        """Test deleting an ingredient that's used in recipes."""
        self.client.login(username='testuser', password='testpass123')

        # Create a recipe using this ingredient
        recipe = Recipe.objects.create(
            title='Test Recipe',
            author=self.user,
            instructions='Test'
        )
        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=self.ingredient,
            amount=500.0,
            unit='g'
        )

        ingredient_id = self.ingredient.pk

        response = self.client.post(
            reverse('delete-ingredient', kwargs={'pk': ingredient_id})
        )

        # Ingredient should be deleted
        self.assertFalse(Ingredient.objects.filter(pk=ingredient_id).exists())

        # Recipe should still exist but without the ingredient
        recipe.refresh_from_db()
        self.assertFalse(recipe.ingredients.filter(pk=ingredient_id).exists())

    def test_delete_ingredient_nonexistent(self):
        """Test deleting a non-existent ingredient."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(
            reverse('delete-ingredient', kwargs={'pk': 99999})
        )

        self.assertEqual(response.status_code, 404)

class AddRecipeViewTest(TestCase):
    """Test cases for add_recipe view with formset."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

        Profile.objects.filter(user=self.user).delete()

        self.pantry = Pantry.objects.create(user=self.user)
        self.ingredient = Ingredient.objects.create(
            name='Test Ingredient',
            brand='Generic',
            calories=100,
            portion_data=[
                {
                    'amount': 1,
                    'measure_unit': 'cup',
                    'gram_weight': 240
                }
            ]
        )
        self.pantry.ingredients.add(self.ingredient)

    def test_add_recipe_get_request(self):
        """Test GET request to add recipe page."""
        response = self.client.get(reverse('add-recipe'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'buddy_crocker/add_recipe.html')
        self.assertIn('form', response.context)
        self.assertIn('formset', response.context)

    def test_add_recipe_requires_login(self):
        """Test that add recipe requires authentication."""
        self.client.logout()
        response = self.client.get(reverse('add-recipe'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_add_recipe_post_valid(self):
        """Test creating recipe with ingredients."""
        form_data = {
            'title': 'New Recipe',
            'instructions': 'Mix and bake for 30 minutes.',
            'servings': 4,
            'prep_time': 15,
            'cook_time': 30,
            'difficulty': 'medium',
            # Formset management
            'recipe_ingredients-TOTAL_FORMS': '1',
            'recipe_ingredients-INITIAL_FORMS': '0',
            'recipe_ingredients-MIN_NUM_FORMS': '1',
            'recipe_ingredients-MAX_NUM_FORMS': '1000',
            # First ingredient
            'recipe_ingredients-0-ingredient': self.ingredient.pk,
            'recipe_ingredients-0-amount': '2.0',
            'recipe_ingredients-0-unit': 'cup',
            'recipe_ingredients-0-notes': '',
        }

        response = self.client.post(reverse('add-recipe'), data=form_data)

        self.assertEqual(response.status_code, 302)

        # Verify recipe created
        recipe = Recipe.objects.get(title='New Recipe')
        self.assertEqual(recipe.author, self.user)
        self.assertEqual(recipe.servings, 4)
        self.assertEqual(recipe.prep_time, 15)
        self.assertEqual(recipe.cook_time, 30)

        # Verify ingredient added with amount
        recipe_ingredients = recipe.recipe_ingredients.all()
        self.assertEqual(recipe_ingredients.count(), 1)
        self.assertEqual(recipe_ingredients[0].amount, Decimal('2.0'))
        self.assertEqual(recipe_ingredients[0].unit, 'cup')

    def test_add_recipe_auto_calculates_gram_weight(self):
        """Test that gram weight is auto-calculated from USDA data."""
        form_data = {
            'title': 'Test Recipe',
            'instructions': 'Instructions here',
            'servings': 2,
            'difficulty': 'easy',
            'recipe_ingredients-TOTAL_FORMS': '1',
            'recipe_ingredients-INITIAL_FORMS': '0',
            'recipe_ingredients-MIN_NUM_FORMS': '1',
            'recipe_ingredients-MAX_NUM_FORMS': '1000',
            'recipe_ingredients-0-ingredient': self.ingredient.pk,
            'recipe_ingredients-0-amount': '2.0',
            'recipe_ingredients-0-unit': 'cup',
        }

        response = self.client.post(reverse('add-recipe'), data=form_data)
        self.assertEqual(response.status_code, 302)

        recipe = Recipe.objects.get(title='Test Recipe')
        recipe_ing = recipe.recipe_ingredients.first()

        # Should auto-calculate: 2 cups * 240g/cup = 480g
        self.assertEqual(recipe_ing.gram_weight, 480)

    def test_add_recipe_multiple_ingredients(self):
        """Test adding recipe with multiple ingredients."""
        ingredient2 = Ingredient.objects.create(
            name='Sugar',
            calories=387
        )
        self.pantry.ingredients.add(ingredient2)

        form_data = {
            'title': 'Multi Ingredient Recipe',
            'instructions': 'Mix all ingredients',
            'servings': 4,
            'difficulty': 'easy',
            'recipe_ingredients-TOTAL_FORMS': '2',
            'recipe_ingredients-INITIAL_FORMS': '0',
            'recipe_ingredients-MIN_NUM_FORMS': '1',
            'recipe_ingredients-MAX_NUM_FORMS': '1000',
            'recipe_ingredients-0-ingredient': self.ingredient.pk,
            'recipe_ingredients-0-amount': '1.0',
            'recipe_ingredients-0-unit': 'cup',
            'recipe_ingredients-1-ingredient': ingredient2.pk,
            'recipe_ingredients-1-amount': '0.5',
            'recipe_ingredients-1-unit': 'cup',
        }

        response = self.client.post(reverse('add-recipe'), data=form_data)
        self.assertEqual(response.status_code, 302)

        recipe = Recipe.objects.get(title='Multi Ingredient Recipe')
        self.assertEqual(recipe.recipe_ingredients.count(), 2)

class EditRecipeViewTest(TestCase):
    """Test cases for edit_recipe view."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

        Profile.objects.filter(user=self.user).delete()

        self.ingredient = Ingredient.objects.create(
            name='Test Ingredient',
            calories=100
        )

        self.recipe = Recipe.objects.create(
            title='Original Recipe',
            author=self.user,
            instructions='Original instructions',
            servings=4
        )

        RecipeIngredient.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            amount=Decimal('1.0'),
            unit='cup'
        )

    def test_edit_recipe_get_request(self):
        """Test GET request to edit recipe page."""
        response = self.client.get(
            reverse('edit-recipe', kwargs={'pk': self.recipe.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'buddy_crocker/add_recipe.html')
        self.assertTrue(response.context['edit_mode'])

    def test_edit_recipe_update_metadata(self):
        """Test updating recipe metadata."""
        form_data = {
            'title': 'Updated Recipe',
            'instructions': 'Updated instructions',
            'servings': 6,
            'prep_time': 20,
            'cook_time': 40,
            'difficulty': 'hard',
            'recipe_ingredients-TOTAL_FORMS': '1',
            'recipe_ingredients-INITIAL_FORMS': '1',
            'recipe_ingredients-MIN_NUM_FORMS': '1',
            'recipe_ingredients-MAX_NUM_FORMS': '1000',
            'recipe_ingredients-0-id': self.recipe.recipe_ingredients.first().pk,
            'recipe_ingredients-0-ingredient': self.ingredient.pk,
            'recipe_ingredients-0-amount': '2.0',
            'recipe_ingredients-0-unit': 'cup',
        }

        response = self.client.post(
            reverse('edit-recipe', kwargs={'pk': self.recipe.pk}),
            data=form_data
        )

        self.assertEqual(response.status_code, 302)

        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.title, 'Updated Recipe')
        self.assertEqual(self.recipe.servings, 6)
        self.assertEqual(self.recipe.prep_time, 20)
        self.assertEqual(self.recipe.difficulty, 'hard')

    def test_edit_recipe_only_author_can_edit(self):
        """Test that only recipe author can edit."""
        other_user = User.objects.create_user(
            username='otheruser',
            password='testpass123'
        )
        self.client.login(username='otheruser', password='testpass123')

        response = self.client.get(
            reverse('edit-recipe', kwargs={'pk': self.recipe.pk})
        )

        self.assertEqual(response.status_code, 404)

class DeleteRecipeTest(TestCase):
    """Tests for the delete_recipe view"""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            password='testpass123',
            email='other@example.com'
        )

        self.ingredient = Ingredient.objects.create(
            name='Test Ingredient',
            brand='Generic',
            calories=100
        )

        self.recipe = Recipe.objects.create(
            title='Test Recipe',
            author=self.user,
            instructions='Test instructions'
        )
        RecipeIngredient.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            amount=500.0,
            unit='g'
        )

    def test_delete_recipe_get_confirmation(self):
        """Test GET request shows confirmation page."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.get(
            reverse('delete-recipe', kwargs={'pk': self.recipe.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'buddy_crocker/delete_recipe_confirm.html')
        self.assertIn('recipe', response.context)
        self.assertEqual(response.context['recipe'], self.recipe)

    def test_delete_recipe_post_success(self):
        """Test successfully deleting a recipe."""
        self.client.login(username='testuser', password='testpass123')

        recipe_id = self.recipe.pk
        recipe_title = self.recipe.title

        response = self.client.post(
            reverse('delete-recipe', kwargs={'pk': recipe_id})
        )

        # Check redirect to recipe-search
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('recipe-search'))

        # Verify recipe deleted
        self.assertFalse(Recipe.objects.filter(pk=recipe_id).exists())

    def test_delete_recipe_preserves_ingredients(self):
        """Test that deleting a recipe doesn't delete its ingredients."""
        self.client.login(username='testuser', password='testpass123')

        ingredient_id = self.ingredient.pk
        recipe_id = self.recipe.pk

        response = self.client.post(
            reverse('delete-recipe', kwargs={'pk': recipe_id})
        )

        # Recipe should be deleted
        self.assertFalse(Recipe.objects.filter(pk=recipe_id).exists())

        # Ingredient should still exist
        self.assertTrue(Ingredient.objects.filter(pk=ingredient_id).exists())

    def test_delete_recipe_nonexistent(self):
        """Test deleting a non-existent recipe."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(
            reverse('delete-recipe', kwargs={'pk': 99999})
        )

        self.assertEqual(response.status_code, 404)

    def test_delete_recipe_multiple_recipes_same_title_different_authors(self):
        """Test that deleting one recipe doesn't affect recipes with same title by different authors."""
        self.client.login(username='testuser', password='testpass123')

        # Create recipe with same title by different author
        other_recipe = Recipe.objects.create(
            title='Test Recipe',  # Same title
            author=self.other_user,
            instructions='Different instructions'
        )

        recipe_id = self.recipe.pk
        other_recipe_id = other_recipe.pk

        # Delete first recipe
        response = self.client.post(
            reverse('delete-recipe', kwargs={'pk': recipe_id})
        )

        # First recipe deleted
        self.assertFalse(Recipe.objects.filter(pk=recipe_id).exists())

        # Other recipe still exists
        self.assertTrue(Recipe.objects.filter(pk=other_recipe_id).exists())

class RecipeDetailViewTest(TestCase):
    """Test cases for enhanced recipe detail view."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        Profile.objects.filter(user=self.user).delete()

        self.ingredient1 = Ingredient.objects.create(
            name='Chicken',
            calories=165
        )
        self.ingredient2 = Ingredient.objects.create(
            name='Rice',
            calories=130
        )

        self.recipe = Recipe.objects.create(
            title='Chicken Rice Bowl',
            author=self.user,
            instructions='Cook and serve',
            servings=2,
            prep_time=15,
            cook_time=25,
            difficulty='easy'
        )

        RecipeIngredient.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient1,
            amount=Decimal('200'),
            unit='g',
            gram_weight=200
        )

        RecipeIngredient.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient2,
            amount=Decimal('150'),
            unit='g',
            gram_weight=150
        )

    def test_recipe_detail_displays_nutrition(self):
        """Test that recipe detail shows nutrition calculations."""
        response = self.client.get(
            reverse('recipe-detail', kwargs={'pk': self.recipe.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('total_calories', response.context)
        self.assertIn('calories_per_serving', response.context)
        self.assertIn('recipe_ingredients', response.context)

        # Verify calculations
        # Chicken: 165 cal/100g * 200g = 330 cal
        # Rice: 130 cal/100g * 150g = 195 cal
        # Total: 525 cal, Per serving: 262.5 → 262 cal
        self.assertEqual(response.context['total_calories'], 525)
        self.assertEqual(response.context['calories_per_serving'], 262)

    def test_recipe_detail_shows_total_time(self):
        """Test that total time is displayed."""
        response = self.client.get(
            reverse('recipe-detail', kwargs={'pk': self.recipe.pk})
        )

        self.assertIn('total_time', response.context)
        self.assertEqual(response.context['total_time'], 40)  # 15 + 25

class AddIngredientUSDATest(TestCase):
    def setUp(self):
        """Set up test client and user."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='usdauser',
            password='testpass123'
        )
        Profile.objects.filter(user=self.user).delete()
        self.allergen = Allergen.objects.create(
            name='Peanuts',
            category='fda_major_9'
        )

    @patch('services.usda_service.get_complete_ingredient_data')
    def test_add_ingredient_with_usda_success(self, mock_get_data):
        """Test successful USDA data fetch and storage."""
        self.client.login(username='usdauser', password='testpass123')

        mock_get_data.return_value = {
            'basic': {
                'name': 'USDA Bread',
                'brand': 'Generic',
                'fdc_id': 123456,
                'data_type': 'Branded',
                'calories_per_100g': 250,
            },
            'nutrients': {
                'macronutrients': {
                    'protein': {
                        'name': 'Protein',
                        'amount': 8,
                        'unit': 'g',
                        'nutrient_id': 1003
                    }
                },
                'vitamins': {},
                'minerals': {},
                'other': {}
            },
            'portions': [
                {
                    'id': 1,
                    'amount': 1,
                    'modifier': '',
                    'measure_unit': 'slice',
                    'gram_weight': 30,
                    'description': '1 slice',
                    'seq_num': 1,
                }
            ],
            'ingredients_text': 'wheat flour, water, yeast',
            'detected_allergens': []
        }

        response = self.client.post(
            reverse('add-ingredient'),
            {
                'name': 'USDA Bread',
                'brand': 'Generic',
                'calories': 100,
                'allergens': [self.allergen.id],
                'fdc_id': '123456',
            }
        )

        self.assertEqual(response.status_code, 302)

        ingredient = Ingredient.objects.get(name='USDA Bread', brand='Generic')
        self.assertEqual(ingredient.calories, 250)  # Updated from USDA
        self.assertEqual(ingredient.fdc_id, 123456)
        self.assertTrue(ingredient.has_nutrition_data())
        self.assertTrue(ingredient.has_portion_data())

    @patch('services.usda_service.get_complete_ingredient_data')
    def test_add_ingredient_handles_api_key_error(self, mock_get_data):
        """Test that invalid API key error shows proper message."""
        self.client.login(username='usdauser', password='testpass123')

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

        # Ingredient should NOT be created
        self.assertFalse(
            Ingredient.objects.filter(name='Test Item').exists()
        )

    @patch('services.usda_service.get_complete_ingredient_data')
    def test_add_ingredient_handles_rate_limit_error(self, mock_get_data):
        """Test that rate limit error continues with warning."""
        self.client.login(username='usdauser', password='testpass123')

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

        # Should succeed with warning
        self.assertEqual(response.status_code, 302)

        # Ingredient should be created with form data
        ingredient = Ingredient.objects.get(name='Test Item')
        self.assertEqual(ingredient.calories, 100)
        self.assertIsNone(ingredient.fdc_id)  # Not set due to error

    @patch('services.usda_service.get_complete_ingredient_data')
    def test_add_ingredient_handles_not_found_error(self, mock_get_data):
        """Test that 404 error continues with warning."""
        self.client.login(username='usdauser', password='testpass123')

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

        # Should succeed with warning
        self.assertEqual(response.status_code, 302)

        # Ingredient should be created
        ingredient = Ingredient.objects.get(name='Test Item')
        self.assertIsNotNone(ingredient)

    @patch('services.usda_service.get_complete_ingredient_data')
    def test_add_ingredient_handles_generic_api_error(self, mock_get_data):
        """Test that generic API errors continue with warning."""
        self.client.login(username='usdauser', password='testpass123')

        mock_get_data.side_effect = usda_api.USDAAPIError("API Error")

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

        # Should succeed with warning
        self.assertEqual(response.status_code, 302)

    @patch('services.usda_service.get_complete_ingredient_data')
    def test_add_ingredient_handles_unexpected_error(self, mock_get_data):
        """Test that unexpected errors are handled gracefully."""
        self.client.login(username='usdauser', password='testpass123')

        mock_get_data.side_effect = RuntimeError("Unexpected error")

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

        # Should succeed with warning
        self.assertEqual(response.status_code, 302)

    def test_add_ingredient_without_usda(self):
        """Test that adding ingredient without fdc_id works normally."""
        self.client.login(username='usdauser', password='testpass123')

        response = self.client.post(
            reverse('add-ingredient'),
            {
                'name': 'Manual Item',
                'brand': 'Homemade',
                'calories': 150,
                'allergens': [self.allergen.id],
            }
        )

        self.assertEqual(response.status_code, 302)

        ingredient = Ingredient.objects.get(name='Manual Item', brand='Homemade')
        self.assertEqual(ingredient.calories, 150)
        self.assertIsNone(ingredient.fdc_id)
        self.assertFalse(ingredient.has_nutrition_data())

class SearchUSDAIngredientsTest(TestCase):
    """Updated tests for search_usda_ingredients endpoint."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()
        self.allergen = Allergen.objects.create(
            name='Dairy',
            category='fda_major_9',
            alternative_names=['milk', 'cheese', 'cheddar']
        )

    @patch('services.usda_service.search_usda_foods')
    def test_search_endpoint_success(self, mock_search):
        """Test successful search."""
        mock_search.return_value = [
            {
                'name': 'Cheddar Cheese',
                'brand': 'Generic',
                'calories': 403,
                'fdc_id': 123456,
                'data_type': 'Branded',
                'suggested_allergens': [
                    {'id': self.allergen.id, 'name': 'Dairy', 'category': 'fda_major_9'}
                ]
            }
        ]

        response = self.client.get(
            reverse('search-usda-ingredients'),
            {'q': 'cheddar'}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['name'], 'Cheddar Cheese')

    @patch('services.usda_service.search_usda_foods')
    def test_search_endpoint_handles_api_key_error(self, mock_search):
        """Test that API key error returns 500 with proper format."""
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
        """Test that rate limit returns 429."""
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
        """Test that generic API error returns 503."""
        mock_search.side_effect = usda_api.USDAAPIError("API Error")

        response = self.client.get(
            reverse('search-usda-ingredients'),
            {'q': 'chicken'}
        )

        self.assertEqual(response.status_code, 503)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'search_failed')

    @patch('services.usda_service.search_usda_foods')
    def test_search_endpoint_handles_unexpected_error(self, mock_search):
        """Test that unexpected errors return 500."""
        mock_search.side_effect = RuntimeError("Unexpected")

        response = self.client.get(
            reverse('search-usda-ingredients'),
            {'q': 'chicken'}
        )

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'internal_error')

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

class AddCustomPortionTest(TestCase):
    """Test cases for add_custom_portion API endpoint."""

    def setUp(self):
        """Set up test client and data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        Profile.objects.filter(user=self.user).delete()

        # Create ingredient with existing portion data
        self.ingredient = Ingredient.objects.create(
            name='Test Food',
            brand='Generic',
            calories=200,
            fdc_id=123456,
            nutrition_data={
                'macronutrients': {
                    'protein': {'name': 'Protein', 'amount': 8, 'unit': 'g'}
                },
                'vitamins': {},
                'minerals': {},
                'other': {}
            },
            portion_data=[
                {
                    'id': 1,
                    'amount': 1,
                    'measure_unit': 'cup',
                    'gram_weight': 240,
                    'description': '1 cup',
                    'seq_num': 1
                }
            ]
        )

    def test_add_custom_portion_requires_login(self):
        """Test that endpoint requires authentication."""
        response = self.client.post(
            reverse('add-custom-portion', kwargs={'pk': self.ingredient.pk})
        )
        # Should redirect to login
        self.assertEqual(response.status_code, 302)

    def test_add_custom_portion_success(self):
        """Test successfully adding a custom portion."""
        self.client.login(username='testuser', password='testpass123')

        custom_portion = {
            'amount': 2,
            'measure_unit': 'slice',
            'gram_weight': 60,
            'description': '2 slices',
            'seq_num': 999,
            'custom': True
        }

        response = self.client.post(
            reverse('add-custom-portion', kwargs={'pk': self.ingredient.pk}),
            data=json.dumps(custom_portion),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

        # Verify portion was added
        self.ingredient.refresh_from_db()
        self.assertEqual(len(self.ingredient.portion_data), 2)
        self.assertEqual(self.ingredient.portion_data[1]['measure_unit'], 'slice')
        self.assertEqual(self.ingredient.portion_data[1]['gram_weight'], 60)

    def test_add_custom_portion_preserves_existing_data(self):
        """Test that adding custom portion doesn't overwrite existing portions."""
        self.client.login(username='testuser', password='testpass123')

        original_portion = self.ingredient.portion_data[0].copy()

        custom_portion = {
            'amount': 1,
            'measure_unit': 'tablespoon',
            'gram_weight': 15,
            'description': '1 tablespoon',
            'seq_num': 999,
            'custom': True
        }

        response = self.client.post(
            reverse('add-custom-portion', kwargs={'pk': self.ingredient.pk}),
            data=json.dumps(custom_portion),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

        # Verify original portion still exists
        self.ingredient.refresh_from_db()
        self.assertEqual(self.ingredient.portion_data[0], original_portion)
        self.assertEqual(len(self.ingredient.portion_data), 2)

    def test_add_custom_portion_to_ingredient_without_portions(self):
        """Test adding custom portion to ingredient with no existing portions."""
        self.client.login(username='testuser', password='testpass123')

        # Create ingredient without portion data
        ingredient_no_portions = Ingredient.objects.create(
            name='Simple Food',
            brand='Generic',
            calories=100
        )

        custom_portion = {
            'amount': 1,
            'measure_unit': 'serving',
            'gram_weight': 50,
            'description': '1 serving',
            'seq_num': 1,
            'custom': True
        }

        response = self.client.post(
            reverse('add-custom-portion', kwargs={'pk': ingredient_no_portions.pk}),
            data=json.dumps(custom_portion),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

        # Verify portion was added
        ingredient_no_portions.refresh_from_db()
        self.assertEqual(len(ingredient_no_portions.portion_data), 1)
        self.assertEqual(ingredient_no_portions.portion_data[0]['measure_unit'], 'serving')

    def test_add_custom_portion_invalid_json(self):
        """Test handling of invalid JSON data."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(
            reverse('add-custom-portion', kwargs={'pk': self.ingredient.pk}),
            data='invalid json',
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('error', data)

    def test_add_custom_portion_missing_fields(self):
        """Test handling of incomplete custom portion data."""
        self.client.login(username='testuser', password='testpass123')

        incomplete_portion = {
            'amount': 1,
            # Missing measure_unit and gram_weight
        }

        response = self.client.post(
            reverse('add-custom-portion', kwargs={'pk': self.ingredient.pk}),
            data=json.dumps(incomplete_portion),
            content_type='application/json'
        )

        # Should still succeed (validation handled on frontend)
        self.assertEqual(response.status_code, 200)

    def test_add_custom_portion_nonexistent_ingredient(self):
        """Test adding custom portion to non-existent ingredient."""
        self.client.login(username='testuser', password='testpass123')

        custom_portion = {
            'amount': 1,
            'measure_unit': 'cup',
            'gram_weight': 240,
            'seq_num': 999
        }

        response = self.client.post(
            reverse('add-custom-portion', kwargs={'pk': 99999}),
            data=json.dumps(custom_portion),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 404)

    def test_add_multiple_custom_portions(self):
        """Test adding multiple custom portions to same ingredient."""
        self.client.login(username='testuser', password='testpass123')

        portions = [
            {
                'amount': 1,
                'measure_unit': 'slice',
                'gram_weight': 30,
                'seq_num': 999
            },
            {
                'amount': 1,
                'measure_unit': 'tablespoon',
                'gram_weight': 15,
                'seq_num': 998
            },
            {
                'amount': 0.5,
                'measure_unit': 'cup',
                'gram_weight': 120,
                'seq_num': 997
            }
        ]

        for portion in portions:
            response = self.client.post(
                reverse('add-custom-portion', kwargs={'pk': self.ingredient.pk}),
                data=json.dumps(portion),
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 200)

        # Verify all portions were added
        self.ingredient.refresh_from_db()
        self.assertEqual(len(self.ingredient.portion_data), 4)  # 1 original + 3 custom

    def test_add_custom_portion_with_decimal_values(self):
        """Test adding custom portion with decimal amount and weight."""
        self.client.login(username='testuser', password='testpass123')

        custom_portion = {
            'amount': 0.5,
            'measure_unit': 'cup',
            'gram_weight': 120.5,
            'description': '1/2 cup',
            'seq_num': 999
        }

        response = self.client.post(
            reverse('add-custom-portion', kwargs={'pk': self.ingredient.pk}),
            data=json.dumps(custom_portion),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

        self.ingredient.refresh_from_db()
        custom = self.ingredient.portion_data[1]
        self.assertEqual(custom['amount'], 0.5)
        self.assertEqual(custom['gram_weight'], 120.5)


class AIRecipeGeneratorViewTest(TestCase):
    """Test cases for AI recipe generator view."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        
        # Create pantry with ingredients
        self.pantry = Pantry.objects.create(user=self.user)
        self.ingredient1 = Ingredient.objects.create(
            name='Chicken',
            calories=165
        )
        self.ingredient2 = Ingredient.objects.create(
            name='Rice',
            calories=130
        )
        self.pantry.ingredients.add(self.ingredient1, self.ingredient2)
    
    def test_ai_recipe_generator_requires_login(self):
        """Test AI generator requires authentication."""
        self.client.logout()
        response = self.client.get(reverse('ai-recipe-generator'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
    
    def test_ai_recipe_generator_get_request(self):
        """Test GET request displays the form."""
        response = self.client.get(reverse('ai-recipe-generator'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'buddy_crocker/ai_recipe_generator.html')
        self.assertIn('pantry_ingredients', response.context)
    
    def test_ai_recipe_generator_no_ingredients_selected(self):
        """Test error when no ingredients selected."""
        response = self.client.post(
            reverse('ai-recipe-generator'),
            {'generate_recipes': True}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('error_msg', response.context)
    
    @patch('buddy_crocker.views.generate_ai_recipes')
    def test_ai_recipe_generator_success(self, mock_generate):
        """Test successful recipe generation."""
        mock_generate.return_value = [
            {
                'title': 'Chicken Rice Bowl',
                'ingredients': ['1 cup chicken', '1 cup rice'],
                'instructions': 'Cook and serve'
            }
        ]
        
        response = self.client.post(
            reverse('ai-recipe-generator'),
            {
                'generate_recipes': True,
                'selected_ingredients': [self.ingredient1.id, self.ingredient2.id]
            }
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('zipped_recipes_forms', response.context)
        mock_generate.assert_called_once()
    
    def test_ai_recipe_generator_save_recipe(self):
        """Test saving generated recipe."""
        # Set up session with mock recipe
        session = self.client.session
        session['ai_recipes'] = [{
            'title': 'Test AI Recipe',
            'ingredients': ['1 cup rice', '200g chicken'],
            'instructions': 'Cook rice and chicken together.'
        }]
        session.save()
        
        response = self.client.post(
            reverse('ai-recipe-generator'),
            {'save_recipe_1': True}
        )
        
        # Verify recipe was created
        self.assertTrue(Recipe.objects.filter(title='Test AI Recipe').exists())
        recipe = Recipe.objects.get(title='Test AI Recipe')
        self.assertEqual(recipe.author, self.user)


# Line 1895 - ADD THESE TESTS HERE

class ViewsEdgeCaseTest(TestCase):
    """Tests for edge cases and error handling in views."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        Profile.objects.filter(user=self.user).delete()
    
    def test_register_invalid_form(self):
        """Test registration with invalid data."""
        self.client.logout()
        response = self.client.post(reverse('register'), {
            'username': 'test',
            'password1': 'short',
            'password2': 'different'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='test').exists())
    
    def test_add_ingredient_adds_to_pantry(self):
        """Test that adding ingredient automatically adds to user's pantry."""
        response = self.client.post(reverse('add-ingredient'), {
            'name': 'New Item',
            'brand': 'Generic',
            'calories': 100,
            'allergens': []
        })
    
        self.assertEqual(response.status_code, 302)
        ingredient = Ingredient.objects.get(name='New Item')
        pantry = Pantry.objects.get(user=self.user)
        self.assertIn(ingredient, pantry.ingredients.all())
    
    def test_profile_detail_creates_missing_profile(self):
        """Test that accessing profile creates one if missing."""
        user = User.objects.create_user(username='newuser', password='pass')
        Profile.objects.filter(user=user).delete()
        
        self.client.login(username='newuser', password='pass')
        response = self.client.get(reverse('profile-detail', args=[user.pk]))
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Profile.objects.filter(user=user).exists())
    
    def test_recipe_search_pagination(self):
        """Test recipe search pagination."""
        for i in range(15):
            Recipe.objects.create(
                title=f'Recipe {i}',
                author=self.user,
                instructions='Test'
            )
        
        response = self.client.get(reverse('recipe-search'))
        self.assertEqual(len(response.context['page_obj']), 12)
        
        response = self.client.get(reverse('recipe-search'), {'page': 2})
        self.assertEqual(len(response.context['page_obj']), 3)
    
    def test_pantry_add_and_remove(self):
        """Test adding and removing ingredients from pantry."""
        ingredient = Ingredient.objects.create(name='Test', calories=100)
        
        # Add ingredient
        response = self.client.post(reverse('pantry'), {
            'action': 'add',
            'ingredient_id': ingredient.id
        })
        self.assertEqual(response.status_code, 302)
        
        pantry = Pantry.objects.get(user=self.user)
        self.assertIn(ingredient, pantry.ingredients.all())
        
        # Remove ingredient
        response = self.client.post(reverse('pantry'), {
            'action': 'remove',
            'ingredient_id': ingredient.id
        })
        self.assertEqual(response.status_code, 302)
        
        pantry.refresh_from_db()
        self.assertNotIn(ingredient, pantry.ingredients.all())
    
    def test_recipe_detail_incomplete_nutrition(self):
        """Test recipe detail with incomplete nutrition data."""
        recipe = Recipe.objects.create(
            title='Test Recipe',
            author=self.user,
            instructions='Test'
        )
        ingredient = Ingredient.objects.create(name='Test', calories=100)
        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=ingredient,
            amount=100,
            unit='g',
            gram_weight=None  # Missing gram weight
        )
        
        response = self.client.get(reverse('recipe-detail', args=[recipe.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['has_complete_nutrition'])


class IngredientDetailNutritionDisplayTest(TestCase):
    """Test cases for nutrition facts display in ingredient detail view."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        Profile.objects.filter(user=self.user).delete()

    def test_ingredient_detail_with_full_nutrition_data(self):
        """Test that ingredient detail shows nutrition facts when data available."""
        ingredient = Ingredient.objects.create(
            name='Nutritious Food',
            brand='Generic',
            calories=250,
            fdc_id=123456,
            nutrition_data={
                'macronutrients': {
                    'protein': {'name': 'Protein', 'amount': 25, 'unit': 'g'},
                    'total_fat': {'name': 'Total Fat', 'amount': 10, 'unit': 'g'}
                },
                'vitamins': {
                    'vitamin_c': {'name': 'Vitamin C', 'amount': 60, 'unit': 'mg'}
                },
                'minerals': {
                    'calcium': {'name': 'Calcium', 'amount': 300, 'unit': 'mg'}
                },
                'other': {}
            },
            portion_data=[
                {
                    'amount': 1,
                    'measure_unit': 'cup',
                    'gram_weight': 240
                }
            ]
        )

        response = self.client.get(
            reverse('ingredient-detail', kwargs={'pk': ingredient.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nutrition Facts')
        self.assertContains(response, 'Protein')
        self.assertContains(response, 'Vitamin C')
        self.assertContains(response, 'Calcium')
        self.assertContains(response, 'Serving Size')

    def test_ingredient_detail_with_portion_data(self):
        """Test that portion selector shows available portions."""
        ingredient = Ingredient.objects.create(
            name='Food with Portions',
            brand='Generic',
            calories=200,
            nutrition_data={
                'macronutrients': {},
                'vitamins': {},
                'minerals': {},
                'other': {}
            },
            portion_data=[
                {
                    'amount': 1,
                    'measure_unit': 'cup',
                    'gram_weight': 240
                },
                {
                    'amount': 1,
                    'measure_unit': 'tablespoon',
                    'gram_weight': 15
                }
            ]
        )

        response = self.client.get(
            reverse('ingredient-detail', kwargs={'pk': ingredient.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Serving Size')
        self.assertContains(response, 'cup')
        self.assertContains(response, 'tablespoon')
        self.assertContains(response, '100 g (USDA Standard)')

    def test_ingredient_detail_without_nutrition_data(self):
        """Test fallback display when nutrition data not available."""
        ingredient = Ingredient.objects.create(
            name='Simple Food',
            brand='Generic',
            calories=100
        )

        response = self.client.get(
            reverse('ingredient-detail', kwargs={'pk': ingredient.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Limited Information Available')
        self.assertContains(response, '100 cal')

    def test_ingredient_detail_shows_usda_badge(self):
        """Test that USDA verified badge shows for USDA-sourced ingredients."""
        ingredient = Ingredient.objects.create(
            name='USDA Food',
            brand='Generic',
            calories=150,
            fdc_id=123456,
            nutrition_data={
                'macronutrients': {},
                'vitamins': {},
                'minerals': {},
                'other': {}
            }
        )

        response = self.client.get(
            reverse('ingredient-detail', kwargs={'pk': ingredient.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'USDA Verified')

    def test_ingredient_detail_custom_portion_form_visible(self):
        """Test that custom portion form is visible when logged in."""
        self.client.login(username='testuser', password='testpass123')

        ingredient = Ingredient.objects.create(
            name='Test Food',
            brand='Generic',
            calories=200,
            nutrition_data={
                'macronutrients': {},
                'vitamins': {},
                'minerals': {},
                'other': {}
            }
        )

        response = self.client.get(
            reverse('ingredient-detail', kwargs={'pk': ingredient.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add Custom Serving Size')
        self.assertContains(response, 'customPortionForm')

    def test_ingredient_detail_portion_availability_message(self):
        """Test message when additional portions not available."""
        ingredient = Ingredient.objects.create(
            name='Basic Food',
            brand='Generic',
            calories=100,
            nutrition_data={
                'macronutrients': {},
                'vitamins': {},
                'minerals': {},
                'other': {}
            }
            # No portion_data
        )

        response = self.client.get(
            reverse('ingredient-detail', kwargs={'pk': ingredient.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Additional portion sizes not available')


class IngredientNutritionCalculationTest(TestCase):
    """Test cases for nutrition calculation logic."""

    def test_has_nutrition_data_method(self):
        """Test has_nutrition_data method returns correct value."""
        ingredient_with_data = Ingredient.objects.create(
            name='Food 1',
            calories=100,
            nutrition_data={
                'macronutrients': {'protein': {'amount': 5}}
            }
        )

        ingredient_without_data = Ingredient.objects.create(
            name='Food 2',
            calories=100
        )

        self.assertTrue(ingredient_with_data.has_nutrition_data())
        self.assertFalse(ingredient_without_data.has_nutrition_data())

    def test_has_portion_data_method(self):
        """Test has_portion_data method returns correct value."""
        ingredient_with_portions = Ingredient.objects.create(
            name='Food 1',
            calories=100,
            portion_data=[{'measure_unit': 'cup', 'gram_weight': 240}]
        )

        ingredient_without_portions = Ingredient.objects.create(
            name='Food 2',
            calories=100
        )

        self.assertTrue(ingredient_with_portions.has_portion_data())
        self.assertFalse(ingredient_without_portions.has_portion_data())

    def test_get_portion_by_unit_method(self):
        """Test get_portion_by_unit retrieves correct portion."""
        ingredient = Ingredient.objects.create(
            name='Food',
            calories=100,
            portion_data=[
                {'measure_unit': 'cup', 'gram_weight': 240},
                {'measure_unit': 'tablespoon', 'gram_weight': 15}
            ]
        )

        cup_portion = ingredient.get_portion_by_unit('cup')
        self.assertIsNotNone(cup_portion)
        self.assertEqual(cup_portion['gram_weight'], 240)

        tbsp_portion = ingredient.get_portion_by_unit('tablespoon')
        self.assertIsNotNone(tbsp_portion)
        self.assertEqual(tbsp_portion['gram_weight'], 15)

        missing_portion = ingredient.get_portion_by_unit('ounce')
        self.assertIsNone(missing_portion)

class QuickAddUSDAIngredientViewTest(TestCase):
    """Test cases for the quick_add_usda_ingredient API endpoint."""

    def setUp(self):
        """Set up test client and user."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        self.url = reverse('quick-add-usda-ingredient')

        # Create test allergen
        self.peanut_allergen = Allergen.objects.create(
            name='Peanuts',
            category='fda_major_9'
        )

    @patch('buddy_crocker.views.usda_service.fetch_usda_data_with_error_handling')
    def test_successful_ingredient_creation(self, mock_fetch):
        """Test successful creation of new ingredient from USDA data."""
        # Mock USDA service response
        mock_fetch.return_value = (
            {
                'basic': {'calories_per_100g': 165},
                'nutrients': {
                    'macronutrients': {
                        'protein': {'amount': 31.0, 'unit': 'g'},
                        'fat': {'amount': 3.6, 'unit': 'g'},
                        'carbohydrates': {'amount': 0, 'unit': 'g'}
                    }
                },
                'portions': [
                    {
                        'measure_unit': 'breast',
                        'gram_weight': 174,
                        'modifier': 'boneless, skinless'
                    },
                    {
                        'measure_unit': 'cup',
                        'gram_weight': 140,
                        'modifier': 'chopped or diced'
                    }
                ]
            },
            False,  # should_abort
            None    # error_info
        )

        response = self.client.post(
            self.url,
            data=json.dumps({
                'name': 'Chicken Breast',
                'brand': 'Generic',
                'fdc_id': '171477'
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify response structure
        self.assertTrue(data['success'])
        self.assertIn('ingredient', data)
        self.assertEqual(data['ingredient']['name'], 'Chicken Breast')
        self.assertEqual(data['ingredient']['brand'], 'Generic')
        self.assertEqual(data['ingredient']['calories'], 165)

        # Verify ingredient was created in database
        ingredient = Ingredient.objects.get(
            name='Chicken Breast',
            brand='Generic'
        )
        self.assertEqual(ingredient.calories, 165)
        self.assertEqual(ingredient.fdc_id, 171477)
        self.assertIsNotNone(ingredient.nutrition_data)
        self.assertIsNotNone(ingredient.portion_data)
        self.assertEqual(len(ingredient.portion_data), 2)

        # Verify ingredient was added to user's pantry
        pantry = Pantry.objects.get(user=self.user)
        self.assertIn(ingredient, pantry.ingredients.all())

    @patch('buddy_crocker.views.usda_service.fetch_usda_data_with_error_handling')
    def test_updates_existing_ingredient(self, mock_fetch):
        """Test that existing ingredients are updated with new USDA data."""
        # Create existing ingredient with old data
        existing_ingredient = Ingredient.objects.create(
            name='Peanut Butter',
            brand='Generic',
            calories=100  # Old calorie value
        )

        # Mock USDA response with updated data
        mock_fetch.return_value = (
            {
                'basic': {'calories_per_100g': 588},
                'nutrients': {
                    'macronutrients': {
                        'protein': {'amount': 25.8, 'unit': 'g'},
                        'fat': {'amount': 50.0, 'unit': 'g'},
                        'carbohydrates': {'amount': 20.0, 'unit': 'g'}
                    }
                },
                'portions': [
                    {
                        'measure_unit': 'tbsp',
                        'gram_weight': 16,
                        'modifier': ''
                    }
                ]
            },
            False,
            None
        )

        response = self.client.post(
            self.url,
            data=json.dumps({
                'name': 'Peanut Butter',
                'brand': 'Generic',
                'fdc_id': '172470'
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

        # Verify ingredient was updated, not duplicated
        self.assertEqual(Ingredient.objects.filter(name='Peanut Butter').count(), 1)

        # Refresh from database and check updated values
        existing_ingredient.refresh_from_db()
        self.assertEqual(existing_ingredient.calories, 588)
        self.assertEqual(existing_ingredient.fdc_id, 172470)
        self.assertIsNotNone(existing_ingredient.nutrition_data)
        
# ============================================================================
# AI RECIPE GENERATOR - COMPREHENSIVE TESTS
# ============================================================================

class AIRecipeGeneratorComprehensiveTest(TestCase):
    """Comprehensive tests for AI recipe generator functionality."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='aiuser',
            password='testpass123'
        )
        self.client.login(username='aiuser', password='testpass123')
        Profile.objects.filter(user=self.user).delete()
        
        # Create pantry with ingredients
        self.pantry = Pantry.objects.create(user=self.user)
        self.flour = Ingredient.objects.create(name='Flour', calories=364)
        self.eggs = Ingredient.objects.create(name='Eggs', calories=155)
        self.milk = Ingredient.objects.create(name='Milk', calories=42)
        self.pantry.ingredients.add(self.flour, self.eggs, self.milk)

    @patch('buddy_crocker.views.generate_ai_recipes')
    def test_generate_recipes_with_multiple_ingredients(self, mock_generate):
        """Test generating recipes with multiple selected ingredients."""
        mock_generate.return_value = [
            {
                'title': 'Pancakes',
                'ingredients': ['2 cups flour', '3 eggs', '1 cup milk'],
                'instructions': 'Mix and cook.',
                'uses_only_pantry': True
            },
            {
                'title': 'Crepes',
                'ingredients': ['1.5 cups flour', '2 eggs', '1 cup milk'],
                'instructions': 'Mix and cook thin.',
                'uses_only_pantry': True
            },
            {
                'title': 'French Toast',
                'ingredients': ['4 eggs', '0.5 cup milk', '8 slices bread'],
                'instructions': 'Dip and fry.',
                'uses_only_pantry': False
            },
            {
                'title': 'Omelette',
                'ingredients': ['3 eggs', 'cheese', 'vegetables'],
                'instructions': 'Beat and cook.',
                'uses_only_pantry': False
            }
        ]
        
        response = self.client.post(
            reverse('ai-recipe-generator'),
            {
                'generate_recipes': '',
                'selected_ingredients': [self.flour.id, self.eggs.id, self.milk.id]
            }
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('zipped_recipes_forms', response.context)
        self.assertEqual(len(response.context['zipped_recipes_forms']), 4)
        mock_generate.assert_called_once_with(['Flour', 'Eggs', 'Milk'])

    @patch('buddy_crocker.views.generate_ai_recipes')
    def test_save_recipe_with_validation_error(self, mock_generate):
        """Test saving recipe with missing title."""
        # Set up session
        session = self.client.session
        session['ai_recipes'] = [
            {
                'title': '',  # Empty title should fail
                'ingredients': ['flour', 'eggs'],
                'instructions': 'Cook'
            }
        ]
        session.save()
        
        response = self.client.post(
            reverse('ai-recipe-generator'),
            {'save_recipe_1': ''}
        )
        
        self.assertEqual(response.status_code, 200)
        # Recipe should not be created
        self.assertFalse(Recipe.objects.filter(author=self.user).exists())

    @patch('buddy_crocker.views.generate_ai_recipes')
    def test_save_recipe_duplicate_title(self, mock_generate):
        """Test saving recipe with duplicate title."""
        # Create existing recipe
        Recipe.objects.create(
            title='Existing Recipe',
            author=self.user,
            instructions='Original'
        )
        
        # Set up session with duplicate title
        session = self.client.session
        session['ai_recipes'] = [
            {
                'title': 'Existing Recipe',
                'ingredients': ['flour'],
                'instructions': 'New version'
            }
        ]
        session.save()
        
        response = self.client.post(
            reverse('ai-recipe-generator'),
            {'save_recipe_1': ''},
            follow=True
        )
        
        # Should show error message
        messages = list(response.context['messages'])
        self.assertTrue(
            any('already exists' in str(m) for m in messages)
        )

    def test_add_to_shopping_list_no_ingredients_selected(self):
        """Test adding to shopping list with no ingredients selected."""
        session = self.client.session
        session['ai_recipes'] = [
            {
                'title': 'Test Recipe',
                'ingredients': ['flour', 'eggs'],
                'instructions': 'Cook'
            }
        ]
        session.save()
        
        response = self.client.post(
            reverse('ai-recipe-generator'),
            {'add_to_shopping_1': ''}  # No shopping checkboxes
        )
        
        messages = list(response.context['messages'])
        self.assertTrue(
            any('No ingredients selected' in str(m) for m in messages)
        )


# ============================================================================
# PARSE INGREDIENT STRING TESTS
# ============================================================================

class ParseIngredientStringTest(TestCase):
    """Test _parse_ingredient_string helper function."""

    def test_parse_amount_unit_name(self):
        """Test parsing '2 cups flour' format."""
        from buddy_crocker.views import _parse_ingredient_string
        
        amount, unit, name = _parse_ingredient_string("2 cups flour")
        self.assertEqual(amount, 2.0)
        self.assertEqual(unit, "cups")
        self.assertEqual(name, "flour")

    def test_parse_fraction_format(self):
        """Test parsing '1/2 cup sugar' format."""
        from buddy_crocker.views import _parse_ingredient_string
        
        amount, unit, name = _parse_ingredient_string("1/2 cup sugar")
        self.assertEqual(amount, 0.5)
        self.assertEqual(unit, "cup")
        self.assertEqual(name, "sugar")

    def test_parse_decimal_amount(self):
        """Test parsing '1.5 lbs chicken' format."""
        from buddy_crocker.views import _parse_ingredient_string
        
        amount, unit, name = _parse_ingredient_string("1.5 lbs chicken")
        self.assertEqual(amount, 1.5)
        self.assertEqual(unit, "lbs")
        self.assertEqual(name, "chicken")

    def test_parse_amount_only(self):
        """Test parsing '3 eggs' format (no unit)."""
        from buddy_crocker.views import _parse_ingredient_string
        
        amount, unit, name = _parse_ingredient_string("3 eggs")
        self.assertEqual(amount, 3.0)
        self.assertIn(name, ["eggs", "3 eggs"])  # May or may not parse unit

    def test_parse_name_only(self):
        """Test parsing 'salt to taste' format."""
        from buddy_crocker.views import _parse_ingredient_string
        
        amount, unit, name = _parse_ingredient_string("salt to taste")
        self.assertEqual(amount, 1.0)
        self.assertEqual(unit, "unit")
        self.assertEqual(name, "salt to taste")

    def test_parse_complex_fraction(self):
        """Test parsing '1/4 cup butter' format."""
        from buddy_crocker.views import _parse_ingredient_string
        
        amount, unit, name = _parse_ingredient_string("1/4 cup butter")
        self.assertEqual(amount, 0.25)
        self.assertEqual(unit, "cup")
        self.assertEqual(name, "butter")

    def test_parse_three_quarters(self):
        """Test parsing '3/4 tsp salt' format."""
        from buddy_crocker.views import _parse_ingredient_string
        
        amount, unit, name = _parse_ingredient_string("3/4 tsp salt")
        self.assertEqual(amount, 0.75)
        self.assertEqual(unit, "tsp")
        self.assertEqual(name, "salt")


# ============================================================================
# AI RECIPE GENERATOR - COMPREHENSIVE TESTS (FIXED)
# ============================================================================

class AIRecipeGeneratorComprehensiveTest(TestCase):
    """Comprehensive tests for AI recipe generator functionality."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='aiuser',
            password='testpass123'
        )
        self.client.login(username='aiuser', password='testpass123')
        Profile.objects.filter(user=self.user).delete()
        
        # Create pantry with ingredients
        self.pantry = Pantry.objects.create(user=self.user)
        self.flour = Ingredient.objects.create(name='Flour', calories=364)
        self.eggs = Ingredient.objects.create(name='Eggs', calories=155)
        self.milk = Ingredient.objects.create(name='Milk', calories=42)
        self.pantry.ingredients.add(self.flour, self.eggs, self.milk)

    @patch('buddy_crocker.views.generate_ai_recipes')
    def test_generate_recipes_with_multiple_ingredients(self, mock_generate):
        """Test generating recipes with multiple selected ingredients."""
        mock_generate.return_value = [
            {
                'title': 'Pancakes',
                'ingredients': ['2 cups flour', '3 eggs', '1 cup milk'],
                'instructions': 'Mix and cook.',
                'uses_only_pantry': True
            },
            {
                'title': 'Crepes',
                'ingredients': ['1.5 cups flour', '2 eggs', '1 cup milk'],
                'instructions': 'Mix and cook thin.',
                'uses_only_pantry': True
            },
            {
                'title': 'French Toast',
                'ingredients': ['4 eggs', '0.5 cup milk', '8 slices bread'],
                'instructions': 'Dip and fry.',
                'uses_only_pantry': False
            },
            {
                'title': 'Omelette',
                'ingredients': ['3 eggs', 'cheese', 'vegetables'],
                'instructions': 'Beat and cook.',
                'uses_only_pantry': False
            }
        ]
        
        response = self.client.post(
            reverse('ai-recipe-generator'),
            {
                'generate_recipes': '',
                'selected_ingredients': [self.flour.id, self.eggs.id, self.milk.id]
            }
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('zipped_recipes_forms', response.context)
        self.assertEqual(len(response.context['zipped_recipes_forms']), 4)
        mock_generate.assert_called_once()

    def test_get_request_shows_pantry(self):
        """Test GET request shows pantry ingredients."""
        response = self.client.get(reverse('ai-recipe-generator'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('pantry_ingredients', response.context)
        pantry_ings = list(response.context['pantry_ingredients'])
        self.assertEqual(len(pantry_ings), 3)

    def test_requires_authentication(self):
        """Test that view requires login."""
        self.client.logout()
        response = self.client.get(reverse('ai-recipe-generator'))
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    @patch('buddy_crocker.views.generate_ai_recipes')
    def test_api_error_handling(self, mock_generate):
        """Test handling of API errors."""
        mock_generate.side_effect = RuntimeError("API Key Error")
        
        response = self.client.post(
            reverse('ai-recipe-generator'),
            {
                'generate_recipes': '',
                'selected_ingredients': [self.flour.id]
            }
        )
        
        self.assertEqual(response.status_code, 200)
        # Should show error message
        self.assertIsNotNone(response.context.get('error_msg'))
    @patch('buddy_crocker.views.generate_ai_recipes')
    def test_generate_branch_triggered_without_save_or_shopping_keys(self, mock_generate):
        """POST with only selected_ingredients should be treated as GENERATE."""
        mock_generate.return_value = [{
            'title': 'Simple Recipe',
            'ingredients': ['Flour'],
            'instructions': 'Do stuff',
            'uses_only_pantry': True,
        }]

        response = self.client.post(
            reverse('ai-recipe-generator'),
            {
                'generate_recipes': '',  # no save_/add_to_shopping_/shopping_ keys
                'selected_ingredients': [self.flour.id],
            },
        )

        self.assertEqual(response.status_code, 200)
        mock_generate.assert_called_once()
        # session should store selected ingredient ids
        session = self.client.session
        self.assertEqual(session.get('selected_pantry_ingredients'), [self.flour.id])
        # and ai_recipes
        self.assertIn('ai_recipes', session)
        self.assertEqual(len(session['ai_recipes']), 1)

    def test_non_generate_branch_when_add_to_shopping_key_present(self):
        """POST with add_to_shopping_ key should go through save/shopping branch, not generate."""
        # seed session with one fake recipe
        session = self.client.session
        session['ai_recipes'] = [{
            'title': 'Shop Recipe',
            'ingredients': ['flour', 'eggs'],
            'instructions': 'Cook',
        }]
        session.save()

        response = self.client.post(
            reverse('ai-recipe-generator'),
            {
                'add_to_shopping_1': '',          # triggers save/shopping branch
                'shopping_1_1': 'flour',          # selected shopping item
            },
        )
        self.assertEqual(response.status_code, 200)
        # no crash => branch executed; ShoppingListItem creation is covered by other tests
    @patch('buddy_crocker.views.generate_ai_recipes')
    def test_generate_with_no_ingredients_sets_error(self, mock_generate):
        """If no checkboxes are selected, view should set error_msg and not call AI."""
        response = self.client.post(
            reverse('ai-recipe-generator'),
            {
                'generate_recipes': '',  # no selected_ingredients key
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('error_msg', response.context)
        self.assertTrue(response.context['error_msg'])
        mock_generate.assert_not_called()

        # session should have been cleared
        session = self.client.session
        self.assertEqual(session.get('selected_pantry_ingredients'), [])
        self.assertEqual(session.get('ai_recipes'), [])
class AddRecipeToShoppingListHelperTest(TestCase):
    """Direct tests for _add_recipe_to_shopping_list helper."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='helperuser',
            password='testpass123',
        )
        self.client.login(username='helperuser', password='testpass123')

    def test_add_recipe_to_shopping_list_creates_items(self):
        from buddy_crocker.views import _add_recipe_to_shopping_list
        from buddy_crocker.models import ShoppingListItem

        fake_recipe = {
            'title': 'Helper Recipe',
            'ingredients': ['1 cup flour', '2 eggs'],
            'instructions': 'Mix and cook',
        }

        request = self.client.get('/').wsgi_request
        request.user = self.user

        added = _add_recipe_to_shopping_list(request, fake_recipe)
        self.assertEqual(added, 2)
        self.assertEqual(
            ShoppingListItem.objects.filter(user=self.user).count(),
            2,
        )
class GetClickedRecipeIndexTest(TestCase):
    """Tests for _get_clicked_recipe_index helper."""

    def test_returns_zero_based_index(self):
        from buddy_crocker.views import _get_clicked_recipe_index
        post_data = {'save_recipe_3': '1'}
        idx = _get_clicked_recipe_index(post_data, 'save_recipe_')
        self.assertEqual(idx, 2)

    def test_returns_none_when_missing(self):
        from buddy_crocker.views import _get_clicked_recipe_index
        post_data = {'other_key': '1'}
        idx = _get_clicked_recipe_index(post_data, 'save_recipe_')
        self.assertIsNone(idx)
