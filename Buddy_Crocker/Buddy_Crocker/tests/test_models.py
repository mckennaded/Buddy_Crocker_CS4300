"""
Unit tests for Buddy Crocker models.

Tests model creation, validation, relationships, and cascading behavior.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.db import IntegrityError
from Buddy_Crocker.models import Allergen, Ingredient, Recipe, Pantry, Profile


class AllergenModelTest(TestCase):
    """Test cases for the Allergen model."""

    def test_allergen_creation(self):
        """Test that an allergen can be created with a name."""
        allergen = Allergen.objects.create(name="Peanuts")
        self.assertEqual(allergen.name, "Peanuts")
        self.assertIsNotNone(allergen.pk)

    def test_allergen_unique_name(self):
        """Test that allergen names must be unique."""
        Allergen.objects.create(name="Shellfish")
        with self.assertRaises(IntegrityError):
            Allergen.objects.create(name="Shellfish")

    def test_allergen_str_representation(self):
        """Test the string representation of an allergen."""
        allergen = Allergen.objects.create(name="Dairy")
        self.assertEqual(str(allergen), "Dairy")


class IngredientModelTest(TestCase):
    """Test cases for the Ingredient model."""

    def setUp(self):
        """Set up test data for ingredient tests."""
        pass

    def test_ingredient_creation(self):
        """Test that an ingredient can be created with required fields."""
        ingredient = Ingredient.objects.create(
            name="Flour",
            calories=364,
            allergens="Gluten"
        )
        self.assertEqual(ingredient.name, "Flour")
        self.assertEqual(ingredient.calories, 364)
        self.assertEqual(ingredient.allergens, "Gluten")

    def test_ingredient_unique_name(self):
        """Test that ingredient names must be unique."""
        Ingredient.objects.create(name="Sugar", calories=387, allergens="")
        with self.assertRaises(IntegrityError):
            Ingredient.objects.create(name="Sugar", calories=400, allergens="")

    def test_ingredient_with_multiple_allergens(self):
        """Test that ingredients can have multiple allergens as a comma-separated string."""
        ingredient = Ingredient.objects.create(
            name="Bread",
            calories=265,
            allergens="Gluten, Soy"
        )
        self.assertEqual(ingredient.allergens, "Gluten, Soy")
        self.assertIn("Gluten", ingredient.allergens)
        self.assertIn("Soy", ingredient.allergens)

    def test_ingredient_no_allergens(self):
        """Test that ingredients can exist without allergens."""
        ingredient = Ingredient.objects.create(name="Water", calories=0, allergens="")
        self.assertEqual(ingredient.allergens, "")

    def test_ingredient_allergens_blank(self):
        """Test that allergens field can be blank."""
        ingredient = Ingredient.objects.create(name="Salt", calories=0)
        self.assertEqual(ingredient.allergens, "")


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
        self.ingredient1 = Ingredient.objects.create(name="Tomato", calories=18, allergens="")
        self.ingredient2 = Ingredient.objects.create(name="Cheese", calories=402, allergens="Dairy")

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

'''
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
'''
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
        #self.ingredient1 = Ingredient.objects.create(name="Eggs", calories=155, allergens="")
        #self.ingredient2 = Ingredient.objects.create(name="Butter", calories=717, allergens="Dairy")

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

''' Sprint 2
    def test_pantry_cascade_delete_with_user(self):
        """Test that deleting a user cascades to delete their pantry."""
        pantry = Pantry.objects.create(user=self.user)
        pantry_id = pantry.pk
        
        self.user.delete()
        
        with self.assertRaises(Pantry.DoesNotExist):
            Pantry.objects.get(pk=pantry_id)
'''
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
        self.allergen1 = Allergen.objects.create(name="Peanuts")
        self.allergen2 = Allergen.objects.create(name="Eggs")

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


class ModelIntegrationTest(TestCase):
    """Integration tests involving multiple models."""

    def setUp(self):
        """Set up complex test data involving multiple models."""
        self.user = User.objects.create_user(
            username="integrationuser",
            password="testpass123"
        )
        '''self.allergen = Allergen.objects.create(name="Lactose")
        self.ingredient = Ingredient.objects.create(
            name="Cream",
            calories=340,
            allergens="Lactose, Dairy"
        )
'''
    # Sprint 2
    '''def test_user_deletion_cascades_to_all_related_models(self):
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
'''
    def test_recipe_with_allergen_information(self):
        """Test that recipes can access allergen info through ingredients."""
        recipe = Recipe.objects.create(
            title="Dessert",
            author=self.user,
            instructions="Mix and bake."
        )
        recipe.ingredients.add(self.ingredient)
        
        # Verify we can access allergen information through ingredient
        recipe_ingredient = recipe.ingredients.first()
        self.assertIn("Lactose", recipe_ingredient.allergens)
        self.assertIn("Dairy", recipe_ingredient.allergens)

    def test_profile_pantry_coordination(self):
        """Test that a user can have both profile allergens and pantry ingredients."""
        profile = Profile.objects.create(user=self.user)
        profile.allergens.add(self.allergen)
        
        # Not implemented yet
       # pantry = Pantry.objects.create(user=self.user)
       # pantry.ingredients.add(self.ingredient)


        # Verify both exist for the same user
        self.assertEqual(self.user.profile.allergens.count(), 1)
        #self.assertEqual(self.user.pantry.ingredients.count(), 1)
        
        # Verify the pantry contains an ingredient with allergen text
        #pantry_ingredient = self.user.pantry.ingredients.first()
        #self.assertIn("Lactose", pantry_ingredient.allergens)