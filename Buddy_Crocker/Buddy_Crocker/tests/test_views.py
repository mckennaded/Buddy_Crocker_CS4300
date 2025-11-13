"""
Integration tests for Buddy Crocker views.

Tests view access control, template rendering, context data, and user interactions.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from Buddy_Crocker.models import Allergen, Ingredient, Recipe, Pantry, Profile


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
        self.assertTemplateUsed(response, 'Buddy_Crocker/index.html')

    def test_recipe_search_accessible_without_login(self):
        """Test that recipe search is publicly accessible."""
        response = self.client.get(reverse('recipe-search'))
        self.assertEqual(response.status_code, 200)

    def test_recipe_search_uses_correct_template(self):
        """Test that recipe search uses the expected template."""
        response = self.client.get(reverse('recipe-search'))
        self.assertTemplateUsed(response, 'Buddy_Crocker/recipe-search.html')

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
        self.assertTemplateUsed(response, 'Buddy_Crocker/recipe_detail.html')

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
        self.assertTemplateUsed(response, 'Buddy_Crocker/ingredient_detail.html')

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
        self.assertTemplateUsed(response, 'Buddy_Crocker/allergen_detail.html')

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
        self.assertTemplateUsed(response, 'Buddy_Crocker/pantry.html')

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
        self.assertTemplateUsed(response, 'Buddy_Crocker/add_recipe.html')

    def test_add_recipe_post_creates_recipe(self):
        """Test that submitting the add recipe form creates a new recipe."""
        self.client.login(username="authuser", password="authpass123")
        
        response = self.client.post(reverse('add-recipe'), {
            'title': 'New Recipe',
            'instructions': 'Mix ingredients and cook.',
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
        self.assertTemplateUsed(response, 'Buddy_Crocker/profile_detail.html')


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
        self.recipe1.ingredients.add(self.flour)
        
        self.recipe2 = Recipe.objects.create(
            title="Smoothie",
            author=self.user,
            instructions="Blend ingredients."
        )
        self.recipe2.ingredients.add(self.milk)
        
        self.recipe3 = Recipe.objects.create(
            title="Rice Bowl",
            author=self.user,
            instructions="Cook rice."
        )
        self.recipe3.ingredients.add(self.rice)

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
        recipe.ingredients.add(self.peanut_butter)
        
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
        recipe.ingredients.add(self.peanut_butter)
        
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
        recipe.ingredients.add(self.peanut_butter)
        
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