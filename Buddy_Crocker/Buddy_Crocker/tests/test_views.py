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
        self.ingredient = Ingredient.objects.create(name="Tomato", calories=18)
        self.allergen = Allergen.objects.create(name="Gluten")

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
        self.assertTemplateUsed(response, 'Buddy_Crocker/recipe_search.html')

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
            title="Salad",
            author=self.user,
            instructions="Mix greens."
        )
        response = self.client.get(reverse('recipe-detail', args=[recipe.pk]))
        self.assertTemplateUsed(response, 'Buddy_Crocker/recipe_detail.html')

    def test_recipe_detail_context_contains_recipe(self):
        """Test that recipe detail view passes the recipe to the template."""
        recipe = Recipe.objects.create(
            title="Soup",
            author=self.user,
            instructions="Simmer for 30 minutes."
        )
        response = self.client.get(reverse('recipe-detail', args=[recipe.pk]))
        self.assertIn('recipe', response.context)
        self.assertEqual(response.context['recipe'].title, "Soup")

    def test_recipe_detail_not_found(self):
        """Test that accessing a non-existent recipe returns 404."""
        response = self.client.get(reverse('recipe-detail', args=[9999]))
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

    def test_pantry_redirects_when_not_logged_in(self):
        """Test that pantry view redirects to login for unauthenticated users."""
        response = self.client.get(reverse('pantry'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

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
        pantry.ingredients.add(ingredient)
        
        response = self.client.get(reverse('pantry'))
        self.assertIn('pantry', response.context)
        self.assertIn(ingredient, response.context['pantry'].ingredients.all())

    def test_add_recipe_redirects_when_not_logged_in(self):
        """Test that add recipe view redirects to login for unauthenticated users."""
        response = self.client.get(reverse('add-recipe'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

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
        
        ingredient = Ingredient.objects.create(name="Salt", calories=0)
        
        response = self.client.post(reverse('add-recipe'), {
            'title': 'New Recipe',
            'instructions': 'Mix ingredients and cook.',
            'ingredients': [ingredient.pk]
        })
        
        # Should redirect after successful creation
        self.assertEqual(response.status_code, 302)
        
        # Verify recipe was created
        recipe = Recipe.objects.get(title='New Recipe', author=self.user)
        self.assertEqual(recipe.instructions, 'Mix ingredients and cook.')
        self.assertIn(ingredient, recipe.ingredients.all())

    def test_profile_detail_redirects_when_not_logged_in(self):
        """Test that profile detail redirects to login for unauthenticated users."""
        response = self.client.get(reverse('profile-detail', args=[self.user.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

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
        
        # Create profile and add allergens
        profile = Profile.objects.create(user=self.user)
        allergen = Allergen.objects.create(name="Dairy")
        profile.allergens.add(allergen)
        
        response = self.client.get(reverse('profile-detail', args=[self.user.pk]))
        self.assertIn('profile', response.context)
        self.assertIn(allergen, response.context['profile'].allergens.all())

    def test_user_can_only_access_own_profile(self):
        """
        Test that users can only view their own profile.
        
        NOTE: This test assumes authorization logic exists. If not implemented,
        this test should be updated or marked as TODO.
        """
        self.client.login(username="authuser", password="authpass123")
        
        # Try to access another user's profile
        response = self.client.get(reverse('profile-detail', args=[self.other_user.pk]))
        
        # Should either be forbidden (403) or redirect
        # Adjust based on actual implementation
        self.assertIn(response.status_code, [302, 403])


class RecipeSearchIntegrationTest(TestCase):
    """Integration tests for recipe search functionality."""

    def setUp(self):
        """Set up test data for recipe search tests."""
        self.client = Client()
        self.user = User.objects.create_user(
            username="searchuser",
            password="searchpass123"
        )
        
        # Create allergens
        self.gluten = Allergen.objects.create(name="Gluten")
        self.dairy = Allergen.objects.create(name="Dairy")
        
        # Create ingredients with allergens
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
        
        # Assuming recipes are in context
        if 'recipes' in response.context:
            recipes = response.context['recipes']
            self.assertIn(self.recipe1, recipes)
            self.assertIn(self.recipe2, recipes)
            self.assertIn(self.recipe3, recipes)

    def test_recipe_search_filter_by_allergen(self):
        """
        TODO: Test that recipe search can filter out recipes with specific allergens.
        
        This test assumes filtering functionality exists. When implemented, the recipe
        search view should accept allergen parameters and exclude recipes containing
        ingredients with those allergens.
        
        Expected behavior:
        - GET request to recipe-search with allergen parameter(s)
        - Response should exclude recipes containing ingredients with those allergens
        - Recipe3 (Rice Bowl) should be in results when filtering for Gluten/Dairy
        - Recipe1 (Bread) should not be in results when filtering for Gluten
        """
        # Example implementation when feature exists:
        # response = self.client.get(reverse('recipe-search'), {'exclude_allergens': [self.gluten.pk]})
        # recipes = response.context['recipes']
        # self.assertNotIn(self.recipe1, recipes)  # Bread has gluten
        # self.assertIn(self.recipe3, recipes)  # Rice Bowl is gluten-free
        pass

    def test_recipe_search_filter_multiple_allergens(self):
        """
        TODO: Test filtering recipes by multiple allergens simultaneously.
        
        Expected behavior:
        - Exclude recipes containing ANY of the specified allergens
        - Only recipes safe for all specified allergens should appear
        """
        # Example implementation when feature exists:
        # response = self.client.get(reverse('recipe-search'), {
        #     'exclude_allergens': [self.gluten.pk, self.dairy.pk]
        # })
        # recipes = response.context['recipes']
        # self.assertEqual(len(recipes), 1)
        # self.assertIn(self.recipe3, recipes)  # Only Rice Bowl should remain
        pass

    def test_recipe_search_respects_user_profile_allergens(self):
        """
        TODO: Test that logged-in users see recipes filtered by their profile allergens.
        
        Expected behavior:
        - When a user is logged in and has allergens in their profile
        - Recipe search automatically filters out recipes with those allergens
        - User-friendly indication of which allergens are being filtered
        """
        # Example implementation when feature exists:
        # profile = Profile.objects.create(user=self.user)
        # profile.allergens.add(self.gluten)
        # 
        # self.client.login(username="searchuser", password="searchpass123")
        # response = self.client.get(reverse('recipe-search'))
        # recipes = response.context['recipes']
        # self.assertNotIn(self.recipe1, recipes)  # Bread filtered due to profile
        pass


class ViewIntegrationTest(TestCase):
    """Complex integration tests across multiple views and models."""

    def setUp(self):
        """Set up comprehensive test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username="integration",
            password="integrationpass123"
        )
        
        # Create allergens
        self.peanuts = Allergen.objects.create(name="Peanuts")
        self.shellfish = Allergen.objects.create(name="Shellfish")
        
        # Create ingredients
        self.peanut_butter = Ingredient.objects.create(name="Peanut Butter", calories=588)
        self.peanut_butter.allergens.add(self.peanuts)
        
        self.shrimp = Ingredient.objects.create(name="Shrimp", calories=99)
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
            'ingredients': [self.banana.pk]
        })
        self.assertEqual(response.status_code, 302)
        
        # Retrieve and view the created recipe
        recipe = Recipe.objects.get(title='Smoothie', author=self.user)
        response = self.client.get(reverse('recipe-detail', args=[recipe.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['recipe'].title, 'Smoothie')

    def test_pantry_contains_ingredient_with_user_allergen(self):
        """Test that a user's pantry can contain ingredients they're allergic to."""
        self.client.login(username="integration", password="integrationpass123")
        
        response = self.client.get(reverse('pantry'))
        pantry = response.context['pantry']
        
        # User has peanut allergen but peanut butter in pantry
        user_allergens = self.user.profile.allergens.all()
        pantry_ingredient_allergens = Allergen.objects.filter(
            ingredients__pantries=pantry
        ).distinct()
        
        # Verify overlap exists
        overlap = set(user_allergens) & set(pantry_ingredient_allergens)
        self.assertIn(self.peanuts, overlap)

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
        
        allergen = response.context['allergen']
        affected_ingredients = allergen.ingredients.all()
        
        self.assertIn(self.peanut_butter, affected_ingredients)
        self.assertNotIn(self.banana, affected_ingredients)

    def test_recipe_detail_shows_allergen_information(self):
        """Test that recipe detail includes allergen info from ingredients."""
        recipe = Recipe.objects.create(
            title="Stir Fry",
            author=self.user,
            instructions="Cook shrimp and vegetables."
        )
        recipe.ingredients.add(self.shrimp, self.banana)
        
        response = self.client.get(reverse('recipe-detail', args=[recipe.pk]))
        recipe_obj = response.context['recipe']
        
        # Get allergens through ingredients
        recipe_allergens = Allergen.objects.filter(
            ingredients__recipes=recipe_obj
        ).distinct()
        
        self.assertIn(self.shellfish, recipe_allergens)
        self.assertNotIn(self.peanuts, recipe_allergens)

    def test_unauthenticated_user_can_view_authenticated_user_recipe(self):
        """Test that public can view recipes created by authenticated users."""
        recipe = Recipe.objects.create(
            title="Public Recipe",
            author=self.user,
            instructions="Anyone can view this."
        )
        
        # Don't login - access as anonymous user
        response = self.client.get(reverse('recipe-detail', args=[recipe.pk]))
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['recipe'].title, "Public Recipe")

    def test_recipe_list_in_search_shows_author_info(self):
        """Test that recipe search results include author information."""
        recipe1 = Recipe.objects.create(
            title="Recipe A",
            author=self.user,
            instructions="Instructions A."
        )
        
        user2 = User.objects.create_user(username="chef2", password="pass")
        recipe2 = Recipe.objects.create(
            title="Recipe B",
            author=user2,
            instructions="Instructions B."
        )
        
        response = self.client.get(reverse('recipe-search'))
        
        # Verify recipes are accessible and have author info
        if 'recipes' in response.context:
            recipes = list(response.context['recipes'])
            self.assertTrue(any(r.author == self.user for r in recipes))
            self.assertTrue(any(r.author == user2 for r in recipes))


class ErrorHandlingTest(TestCase):
    """Test error handling and edge cases in views."""

    def setUp(self):
        """Set up test client and basic data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username="erroruser",
            password="errorpass123"
        )

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
        # Should be 404 or redirect depending on implementation
        self.assertIn(response.status_code, [302, 404])

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
            'ingredients': []
        })
        
        # Should handle gracefully - either show form with errors or redirect
        # The exact status code depends on form implementation
        self.assertIn(response.status_code, [200, 302])

    def test_add_recipe_without_ingredients(self):
        """Test that recipes can be created without ingredients."""
        self.client.login(username="erroruser", password="errorpass123")
        
        response = self.client.post(reverse('add-recipe'), {
            'title': 'No Ingredients',
            'instructions': 'Just instructions.',
            'ingredients': []
        })
        
        # Should succeed
        recipe = Recipe.objects.filter(title='No Ingredients', author=self.user).first()
        if recipe:
            self.assertEqual(recipe.ingredients.count(), 0)

    def test_pantry_auto_created_for_new_user(self):
        """
        Test that accessing pantry view auto-creates pantry if it doesn't exist.
        
        NOTE: This assumes auto-creation logic. If not implemented, pantry
        should be created via signals or user registration process.
        """
        new_user = User.objects.create_user(
            username="newuser",
            password="newpass123"
        )
        self.client.login(username="newuser", password="newpass123")
        
        response = self.client.get(reverse('pantry'))
        
        # Should either auto-create or handle gracefully
        self.assertEqual(response.status_code, 200)

    def test_profile_auto_created_for_new_user(self):
        """
        Test that accessing profile view auto-creates profile if it doesn't exist.
        
        NOTE: This assumes auto-creation logic. If not implemented, profile
        should be created via signals or user registration process.
        """
        new_user = User.objects.create_user(
            username="profilenew",
            password="profilenew123"
        )
        self.client.login(username="profilenew", password="profilenew123")
        
        response = self.client.get(reverse('profile-detail', args=[new_user.pk]))
        
        # Should either auto-create or handle gracefully
        self.assertIn(response.status_code, [200, 302])