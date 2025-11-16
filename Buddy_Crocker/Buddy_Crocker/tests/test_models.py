"""
Unit tests for Buddy Crocker models.

Tests model creation, validation, relationships, and cascading behavior.
Updated to reflect current design with brand field and unique_together constraints.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.db import IntegrityError
from buddy_crocker.models import Allergen, Ingredient, Recipe, Pantry, Profile


class AllergenModelTest(TestCase):
    """Test cases for the Allergen model."""

    def test_allergen_creation(self):
        """Test that an allergen can be created with a name."""
        allergen = Allergen.objects.create(name="Peanuts")
        self.assertEqual(allergen.name, "Peanuts")
        self.assertIsNotNone(allergen.pk)

    def test_allergen_creation_with_all_fields(self):
        """Test that an allergen can be created with all fields."""
        allergen = Allergen.objects.create(
            name="Milk",
            category="fda_major_9",
            alternative_names=["dairy", "lactose", "casein"],
            description="Milk and dairy products",
            usda_search_terms=["milk", "dairy", "lactose"]
        )
        self.assertEqual(allergen.name, "Milk")
        self.assertEqual(allergen.category, "fda_major_9")
        self.assertIn("dairy", allergen.alternative_names)
        self.assertEqual(len(allergen.usda_search_terms), 3)

    def test_allergen_unique_name(self):
        """Test that allergen names must be unique."""
        Allergen.objects.create(name="Shellfish")
        with self.assertRaises(IntegrityError):
            Allergen.objects.create(name="Shellfish")

    def test_allergen_str_representation(self):
        """Test the string representation of an allergen."""
        allergen = Allergen.objects.create(name="Dairy")
        self.assertEqual(str(allergen), "Dairy")

    def test_allergen_default_category(self):
        """Test that allergen has default category of 'custom'."""
        allergen = Allergen.objects.create(name="CustomAllergen")
        self.assertEqual(allergen.category, "custom")

    def test_allergen_category_choices(self):
        """Test that allergen category accepts valid choices."""
        allergen1 = Allergen.objects.create(name="Test1", category="fda_major_9")
        allergen2 = Allergen.objects.create(name="Test2", category="dietary_preference")
        allergen3 = Allergen.objects.create(name="Test3", category="custom")
        
        self.assertEqual(allergen1.category, "fda_major_9")
        self.assertEqual(allergen2.category, "dietary_preference")
        self.assertEqual(allergen3.category, "custom")

    def test_allergen_alternative_names_default(self):
        """Test that alternative_names defaults to empty list."""
        allergen = Allergen.objects.create(name="Test")
        self.assertEqual(allergen.alternative_names, [])

    def test_allergen_ordering(self):
        """Test that allergens are ordered by name."""
        Allergen.objects.create(name="Zinc")
        Allergen.objects.create(name="Apple")
        Allergen.objects.create(name="Milk")
        
        allergens = list(Allergen.objects.all())
        self.assertEqual(allergens[0].name, "Apple")
        self.assertEqual(allergens[1].name, "Milk")
        self.assertEqual(allergens[2].name, "Zinc")


class IngredientModelTest(TestCase):
    """Test cases for the Ingredient model."""

    def setUp(self):
        """Set up test data for ingredient tests."""
        self.allergen1 = Allergen.objects.create(name="Gluten")
        self.allergen2 = Allergen.objects.create(name="Dairy")

    def test_ingredient_creation(self):
        """Test that an ingredient can be created with required fields."""
        ingredient = Ingredient.objects.create(
            name="Flour",
            calories=364
        )
        self.assertEqual(ingredient.name, "Flour")
        self.assertEqual(ingredient.calories, 364)
        self.assertEqual(ingredient.brand, "Generic")  # Default brand

    def test_ingredient_creation_with_brand(self):
        """Test that an ingredient can be created with a brand."""
        ingredient = Ingredient.objects.create(
            name="Peanut Butter",
            brand="Jif",
            calories=190
        )
        self.assertEqual(ingredient.name, "Peanut Butter")
        self.assertEqual(ingredient.brand, "Jif")
        self.assertEqual(ingredient.calories, 190)

    def test_ingredient_unique_name_brand_combination(self):
        """Test that name+brand combination must be unique."""
        Ingredient.objects.create(name="Sugar", brand="Generic", calories=387)
        with self.assertRaises(IntegrityError):
            Ingredient.objects.create(name="Sugar", brand="Generic", calories=400)

    def test_ingredient_same_name_different_brands_allowed(self):
        """Test that same name with different brands is allowed."""
        ingredient1 = Ingredient.objects.create(name="Cheese", brand="Kraft", calories=110)
        ingredient2 = Ingredient.objects.create(name="Cheese", brand="Sargento", calories=100)
        
        self.assertIsNotNone(ingredient1.pk)
        self.assertIsNotNone(ingredient2.pk)
        self.assertNotEqual(ingredient1.pk, ingredient2.pk)

    def test_ingredient_with_allergens_m2m(self):
        """Test that ingredients can have multiple allergens via M2M relationship."""
        ingredient = Ingredient.objects.create(
            name="Bread",
            calories=265
        )
        ingredient.allergens.add(self.allergen1, self.allergen2)
        
        self.assertEqual(ingredient.allergens.count(), 2)
        self.assertIn(self.allergen1, ingredient.allergens.all())
        self.assertIn(self.allergen2, ingredient.allergens.all())

    def test_ingredient_no_allergens(self):
        """Test that ingredients can exist without allergens."""
        ingredient = Ingredient.objects.create(name="Water", calories=0)
        self.assertEqual(ingredient.allergens.count(), 0)

    def test_ingredient_allergens_blank(self):
        """Test that allergens field can be blank."""
        ingredient = Ingredient.objects.create(name="Salt", calories=0)
        self.assertEqual(ingredient.allergens.count(), 0)

    def test_ingredient_reverse_relationship_to_allergen(self):
        """Test the reverse relationship from allergen to ingredients."""
        ingredient = Ingredient.objects.create(name="Milk", calories=42)
        ingredient.allergens.add(self.allergen2)
        
        self.assertIn(ingredient, self.allergen2.ingredients.all())

    def test_ingredient_can_add_remove_allergens(self):
        """Test that allergens can be added and removed from ingredients."""
        ingredient = Ingredient.objects.create(name="Cheese", calories=402)
        
        ingredient.allergens.add(self.allergen2)
        self.assertEqual(ingredient.allergens.count(), 1)
        
        ingredient.allergens.remove(self.allergen2)
        self.assertEqual(ingredient.allergens.count(), 0)

    def test_ingredient_str_with_brand(self):
        """Test string representation with non-generic brand."""
        ingredient = Ingredient.objects.create(
            name="Peanut Butter",
            brand="Jif",
            calories=190
        )
        self.assertEqual(str(ingredient), "Peanut Butter (Jif)")

    def test_ingredient_str_without_brand(self):
        """Test string representation with generic brand."""
        ingredient = Ingredient.objects.create(
            name="Apple",
            brand="Generic",
            calories=95
        )
        self.assertEqual(str(ingredient), "Apple")

    def test_ingredient_ordering(self):
        """Test that ingredients are ordered by name, then brand."""
        Ingredient.objects.create(name="Cheese", brand="Kraft", calories=100)
        Ingredient.objects.create(name="Cheese", brand="Generic", calories=95)
        Ingredient.objects.create(name="Apple", brand="Generic", calories=52)
        
        ingredients = list(Ingredient.objects.all())
        
        self.assertEqual(ingredients[0].name, "Apple")
        self.assertEqual(ingredients[1].name, "Cheese")
        self.assertEqual(ingredients[1].brand, "Generic")
        self.assertEqual(ingredients[2].name, "Cheese")
        self.assertEqual(ingredients[2].brand, "Kraft")


class RecipeModelTest(TestCase):
    """Test cases for the Recipe model."""

    def setUp(self):
        """Set up test user and ingredients for recipe tests."""
        self.user1 = User.objects.create_user(
            username="chef1",
            password="testpass123"
        )
        self.user2 = User.objects.create_user(
            username="chef2",
            password="testpass456"
        )
        
        self.allergen1 = Allergen.objects.create(name="Dairy")
        self.allergen2 = Allergen.objects.create(name="Gluten")
        
        self.ingredient1 = Ingredient.objects.create(name="Tomato", calories=18)
        self.ingredient2 = Ingredient.objects.create(name="Cheese", calories=402)
        self.ingredient2.allergens.add(self.allergen1)

        # Delete any auto-created profiles
        Profile.objects.filter(user=self.user1).delete()
        Profile.objects.filter(user=self.user2).delete()

    def test_recipe_creation(self):
        """Test that a recipe can be created with required fields."""
        recipe = Recipe.objects.create(
            title="Pasta",
            author=self.user1,
            instructions="Boil pasta, add sauce."
        )
        self.assertEqual(recipe.title, "Pasta")
        self.assertEqual(recipe.author, self.user1)
        self.assertEqual(recipe.instructions, "Boil pasta, add sauce.")

    def test_recipe_ingredients_relationship(self):
        """Test that recipes can have multiple ingredients."""
        recipe = Recipe.objects.create(
            title="Pizza",
            author=self.user1,
            instructions="Bake at 450F."
        )
        recipe.ingredients.add(self.ingredient1, self.ingredient2)
        
        self.assertEqual(recipe.ingredients.count(), 2)
        self.assertIn(self.ingredient1, recipe.ingredients.all())

    def test_recipe_get_allergens_method(self):
        """Test that get_allergens returns all allergens from ingredients."""
        recipe = Recipe.objects.create(
            title="Pizza",
            author=self.user1,
            instructions="Bake at 450F."
        )
        recipe.ingredients.add(self.ingredient2)  # Has Dairy allergen
        
        allergens = recipe.get_allergens()
        self.assertEqual(allergens.count(), 1)
        self.assertIn(self.allergen1, allergens)

    def test_recipe_unique_together_constraint(self):
        """Test that title and author combination must be unique."""
        Recipe.objects.create(
            title="Salad",
            author=self.user1,
            instructions="Mix greens."
        )
        
        # Same title but different author should work
        recipe2 = Recipe.objects.create(
            title="Salad",
            author=self.user2,
            instructions="Different recipe."
        )
        self.assertIsNotNone(recipe2.pk)
        
        # Same title and author should fail
        with self.assertRaises(IntegrityError):
            Recipe.objects.create(
                title="Salad",
                author=self.user1,
                instructions="Duplicate."
            )

    def test_recipe_cascade_delete_with_user(self):
        """Test that deleting a user cascades to delete their recipes."""
        recipe = Recipe.objects.create(
            title="Soup",
            author=self.user1,
            instructions="Simmer for 30 minutes."
        )
        recipe_id = recipe.pk
        
        self.user1.delete()
        
        with self.assertRaises(Recipe.DoesNotExist):
            Recipe.objects.get(pk=recipe_id)

    def test_ingredient_reverse_relationship(self):
        """Test the reverse relationship from ingredient to recipes."""
        recipe = Recipe.objects.create(
            title="Sandwich",
            author=self.user1,
            instructions="Assemble ingredients."
        )
        recipe.ingredients.add(self.ingredient1)
        
        self.assertIn(recipe, self.ingredient1.recipes.all())


class PantryModelTest(TestCase):
    """Test cases for the Pantry model."""

    def setUp(self):
        """Set up test user and ingredients for pantry tests."""
        self.user = User.objects.create_user(
            username="pantryuser",
            password="testpass123"
        )
        self.ingredient1 = Ingredient.objects.create(name="Eggs", calories=155)
        self.ingredient2 = Ingredient.objects.create(name="Butter", calories=717)

        # Delete any auto-created profile
        Profile.objects.filter(user=self.user).delete()

    def test_pantry_creation(self):
        """Test that a pantry can be created for a user."""
        pantry = Pantry.objects.create(user=self.user)
        self.assertEqual(pantry.user, self.user)
        self.assertIsNotNone(pantry.pk)

    def test_pantry_one_to_one_relationship(self):
        """Test that each user can have only one pantry."""
        Pantry.objects.create(user=self.user)
        
        with self.assertRaises(IntegrityError):
            Pantry.objects.create(user=self.user)

    def test_pantry_ingredients_relationship(self):
        """Test that pantries can contain multiple ingredients."""
        pantry = Pantry.objects.create(user=self.user)
        pantry.ingredients.add(self.ingredient1, self.ingredient2)
        
        self.assertEqual(pantry.ingredients.count(), 2)
        self.assertIn(self.ingredient1, pantry.ingredients.all())

    def test_pantry_cascade_delete_with_user(self):
        """Test that deleting a user cascades to delete their pantry."""
        pantry = Pantry.objects.create(user=self.user)
        pantry_id = pantry.pk
        
        self.user.delete()
        
        with self.assertRaises(Pantry.DoesNotExist):
            Pantry.objects.get(pk=pantry_id)

    def test_pantry_empty_ingredients(self):
        """Test that a pantry can exist without ingredients."""
        pantry = Pantry.objects.create(user=self.user)
        self.assertEqual(pantry.ingredients.count(), 0)

    def test_ingredient_reverse_relationship(self):
        """Test the reverse relationship from ingredient to pantries."""
        pantry = Pantry.objects.create(user=self.user)
        pantry.ingredients.add(self.ingredient1)
        
        self.assertIn(pantry, self.ingredient1.pantries.all())


class ProfileModelTest(TestCase):
    """Test cases for the Profile model."""

    def setUp(self):
        """Set up test user and allergens for profile tests."""
        self.user = User.objects.create_user(
            username="profileuser",
            password="testpass123"
        )
        self.allergen1 = Allergen.objects.create(name="Nuts")
        self.allergen2 = Allergen.objects.create(name="Eggs")

        # Delete any auto-created profile
        Profile.objects.filter(user=self.user).delete()

    def test_profile_creation(self):
        """Test that a profile can be created for a user."""
        profile = Profile.objects.create(user=self.user)
        self.assertEqual(profile.user, self.user)
        self.assertIsNotNone(profile.pk)

    def test_profile_one_to_one_relationship(self):
        """Test that each user can have only one profile."""
        Profile.objects.create(user=self.user)
        
        with self.assertRaises(IntegrityError):
            Profile.objects.create(user=self.user)

    def test_profile_allergens_relationship(self):
        """Test that profiles can track multiple allergens."""
        profile = Profile.objects.create(user=self.user)
        profile.allergens.add(self.allergen1, self.allergen2)
        
        self.assertEqual(profile.allergens.count(), 2)
        self.assertIn(self.allergen1, profile.allergens.all())

    def test_profile_cascade_delete_with_user(self):
        """Test that deleting a user cascades to delete their profile."""
        profile = Profile.objects.create(user=self.user)
        profile_id = profile.pk
        
        self.user.delete()
        
        with self.assertRaises(Profile.DoesNotExist):
            Profile.objects.get(pk=profile_id)

    def test_profile_no_allergens(self):
        """Test that a profile can exist without allergens."""
        profile = Profile.objects.create(user=self.user)
        self.assertEqual(profile.allergens.count(), 0)

    def test_allergen_reverse_relationship(self):
        """Test the reverse relationship from allergen to profiles."""
        profile = Profile.objects.create(user=self.user)
        profile.allergens.add(self.allergen1)
        
        self.assertIn(profile, self.allergen1.profiles.all())

    def test_profile_get_safe_recipes_no_allergens(self):
        """Test get_safe_recipes returns all recipes when no allergens."""
        profile = Profile.objects.create(user=self.user)
        
        recipe = Recipe.objects.create(
            title="Test Recipe",
            author=self.user,
            instructions="Test"
        )
        
        safe_recipes = profile.get_safe_recipes()
        self.assertIn(recipe, safe_recipes)

    def test_profile_get_safe_recipes_with_allergens(self):
        """Test get_safe_recipes filters out recipes with user's allergens."""
        profile = Profile.objects.create(user=self.user)
        profile.allergens.add(self.allergen1)
        
        # Create ingredient with allergen
        ingredient = Ingredient.objects.create(name="Peanuts", calories=567)
        ingredient.allergens.add(self.allergen1)
        
        # Create unsafe recipe
        unsafe_recipe = Recipe.objects.create(
            title="Unsafe Recipe",
            author=self.user,
            instructions="Contains allergen"
        )
        unsafe_recipe.ingredients.add(ingredient)
        
        # Create safe recipe
        safe_ingredient = Ingredient.objects.create(name="Rice", calories=130)
        safe_recipe = Recipe.objects.create(
            title="Safe Recipe",
            author=self.user,
            instructions="No allergens"
        )
        safe_recipe.ingredients.add(safe_ingredient)
        
        safe_recipes = profile.get_safe_recipes()
        self.assertNotIn(unsafe_recipe, safe_recipes)
        self.assertIn(safe_recipe, safe_recipes)


class ModelIntegrationTest(TestCase):
    """Integration tests involving multiple models."""

    def setUp(self):
        """Set up complex test data involving multiple models."""
        self.user = User.objects.create_user(
            username="integrationuser",
            password="testpass123"
        )
        self.allergen = Allergen.objects.create(name="Lactose", category="fda_major_9")
        self.ingredient = Ingredient.objects.create(
            name="Cream",
            brand="Generic",
            calories=340
        )
        self.ingredient.allergens.add(self.allergen)

        # Delete any auto-created profile
        Profile.objects.filter(user=self.user).delete()

    def test_user_deletion_cascades_to_all_related_models(self):
        """Test that deleting a user cascades to recipe, pantry, and profile."""
        # Create related objects
        recipe = Recipe.objects.create(
            title="Ice Cream",
            author=self.user,
            instructions="Freeze the cream."
        )
        pantry = Pantry.objects.create(user=self.user)
        profile = Profile.objects.create(user=self.user)
        
        recipe_id = recipe.pk
        pantry_id = pantry.pk
        profile_id = profile.pk
        
        # Delete user and verify cascade
        self.user.delete()
        
        with self.assertRaises(Recipe.DoesNotExist):
            Recipe.objects.get(pk=recipe_id)
        with self.assertRaises(Pantry.DoesNotExist):
            Pantry.objects.get(pk=pantry_id)
        with self.assertRaises(Profile.DoesNotExist):
            Profile.objects.get(pk=profile_id)

    def test_recipe_with_allergen_information(self):
        """Test that recipes can access allergen info through ingredients."""
        recipe = Recipe.objects.create(
            title="Dessert",
            author=self.user,
            instructions="Mix and bake."
        )
        recipe.ingredients.add(self.ingredient)
        
        # Verify we can access allergen information through ingredient
        recipe_allergens = recipe.get_allergens()
        self.assertEqual(recipe_allergens.count(), 1)
        self.assertIn(self.allergen, recipe_allergens)

    def test_profile_pantry_coordination(self):
        """Test that a user can have both profile allergens and pantry ingredients."""
        profile = Profile.objects.create(user=self.user)
        profile.allergens.add(self.allergen)
        
        pantry = Pantry.objects.create(user=self.user)
        pantry.ingredients.add(self.ingredient)
        
        # Verify both exist for the same user
        self.assertEqual(self.user.profile.allergens.count(), 1)
        self.assertEqual(self.user.pantry.ingredients.count(), 1)
        
        # Verify the pantry contains an ingredient with the allergen
        pantry_ingredient = self.user.pantry.ingredients.first()
        self.assertIn(self.allergen, pantry_ingredient.allergens.all())

    def test_allergen_affects_multiple_ingredients(self):
        """Test that one allergen can be associated with multiple ingredients."""
        ingredient2 = Ingredient.objects.create(name="Milk", calories=42)
        ingredient2.allergens.add(self.allergen)
        
        affected_ingredients = self.allergen.ingredients.all()
        self.assertEqual(affected_ingredients.count(), 2)
        self.assertIn(self.ingredient, affected_ingredients)
        self.assertIn(ingredient2, affected_ingredients)

    def test_branded_ingredients_in_recipes(self):
        """Test that branded ingredients work properly in recipes."""
        branded_ingredient = Ingredient.objects.create(
            name="Peanut Butter",
            brand="Jif",
            calories=190
        )
        
        recipe = Recipe.objects.create(
            title="PB Sandwich",
            author=self.user,
            instructions="Spread on bread."
        )
        recipe.ingredients.add(branded_ingredient)
        
        self.assertIn(branded_ingredient, recipe.ingredients.all())
        self.assertEqual(str(branded_ingredient), "Peanut Butter (Jif)")