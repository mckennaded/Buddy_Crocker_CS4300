"""
Unit tests for Buddy Crocker models.

Tests model creation, validation, relationships, and cascading behavior.
Updated to reflect current design with brand field and unique_together constraints.
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.urls import reverse
from buddy_crocker.models import Allergen, Ingredient, Recipe, RecipeIngredient, Pantry, Profile


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
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testchef',
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

    def test_recipe_creation_with_new_fields(self):
        """Test creating recipe with servings, time, and difficulty."""
        recipe = Recipe.objects.create(
            title='Chicken and Rice',
            author=self.user,
            instructions='Cook and serve',
            servings=4,
            prep_time=15,
            cook_time=30,
            difficulty='medium'
        )

        self.assertEqual(recipe.servings, 4)
        self.assertEqual(recipe.prep_time, 15)
        self.assertEqual(recipe.cook_time, 30)
        self.assertEqual(recipe.difficulty, 'medium')

    def test_recipe_default_values(self):
        """Test default values for new fields."""
        recipe = Recipe.objects.create(
            title='Simple Recipe',
            author=self.user,
            instructions='Easy instructions'
        )

        self.assertEqual(recipe.servings, 4)  # Default
        self.assertEqual(recipe.difficulty, 'medium')  # Default
        self.assertIsNone(recipe.prep_time)
        self.assertIsNone(recipe.cook_time)

    def test_recipe_get_total_time(self):
        """Test total time calculation."""
        recipe = Recipe.objects.create(
            title='Test Recipe',
            author=self.user,
            instructions='Instructions',
            prep_time=20,
            cook_time=40
        )

        self.assertEqual(recipe.get_total_time(), 60)

    def test_recipe_get_total_time_partial(self):
        """Test total time with only prep or cook time."""
        recipe1 = Recipe.objects.create(
            title='Recipe 1',
            author=self.user,
            instructions='Instructions',
            prep_time=15
        )
        self.assertEqual(recipe1.get_total_time(), 15)

        recipe2 = Recipe.objects.create(
            title='Recipe 2',
            author=self.user,
            instructions='Instructions',
            cook_time=30
        )
        self.assertEqual(recipe2.get_total_time(), 30)

    def test_recipe_get_total_time_none(self):
        """Test total time when neither prep nor cook time specified."""
        recipe = Recipe.objects.create(
            title='Recipe',
            author=self.user,
            instructions='Instructions'
        )

        self.assertIsNone(recipe.get_total_time())

    def test_recipe_calculate_total_calories(self):
        """Test total calorie calculation for recipe."""
        recipe = Recipe.objects.create(
            title='Chicken Rice Bowl',
            author=self.user,
            instructions='Mix and serve',
            servings=2
        )

        # Add ingredients with gram weights
        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=self.ingredient1,
            amount=Decimal('200'),
            unit='g',
            gram_weight=200  # 165 cal/100g * 200g = 330 cal
        )

        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=self.ingredient2,
            amount=Decimal('150'),
            unit='g',
            gram_weight=150  # 130 cal/100g * 150g = 195 cal
        )

        total = recipe.calculate_total_calories()
        self.assertEqual(total, 525)  # 330 + 195

    def test_recipe_calculate_calories_per_serving(self):
        """Test per-serving calorie calculation."""
        recipe = Recipe.objects.create(
            title='Test Recipe',
            author=self.user,
            instructions='Instructions',
            servings=4
        )

        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=self.ingredient1,
            amount=Decimal('400'),
            unit='g',
            gram_weight=400  # 660 cal
        )

        calories_per_serving = recipe.calculate_calories_per_serving()
        self.assertEqual(calories_per_serving, 165)  # 660 / 4

    def test_recipe_calculate_calories_per_serving_zero_servings(self):
        """Test calorie calculation handles zero servings gracefully."""
        recipe = Recipe.objects.create(
            title='Test Recipe',
            author=self.user,
            instructions='Instructions',
            servings=0  # Invalid but should be handled
        )

        calories = recipe.calculate_calories_per_serving()
        self.assertEqual(calories, 0)

    def test_recipe_get_allergens(self):
        """Test getting allergens from recipe ingredients."""
        allergen = Allergen.objects.create(name='Gluten')
        self.ingredient1.allergens.add(allergen)

        recipe = Recipe.objects.create(
            title='Test Recipe',
            author=self.user,
            instructions='Instructions'
        )

        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=self.ingredient1,
            amount=Decimal('1'),
            unit='serving'
        )

        allergens = recipe.get_allergens()
        self.assertEqual(allergens.count(), 1)
        self.assertIn(allergen, allergens)

    def test_recipe_get_ingredient_list(self):
        """Test getting formatted ingredient list."""
        recipe = Recipe.objects.create(
            title='Test Recipe',
            author=self.user,
            instructions='Instructions'
        )

        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=self.ingredient1,
            amount=Decimal('2'),
            unit='cup',
            order=1
        )

        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=self.ingredient2,
            amount=Decimal('1'),
            unit='cup',
            order=0
        )

        ingredients = recipe.get_ingredient_list()
        self.assertEqual(len(ingredients), 2)
        # Should be ordered by order field
        self.assertEqual(ingredients[0].ingredient, self.ingredient2)
        self.assertEqual(ingredients[1].ingredient, self.ingredient1)

    def test_recipe_has_complete_nutrition_data(self):
        """Test checking if recipe has complete nutrition data."""
        recipe = Recipe.objects.create(
            title='Test Recipe',
            author=self.user,
            instructions='Instructions'
        )

        # Add ingredient with gram weight
        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=self.ingredient1,
            amount=Decimal('1'),
            unit='cup',
            gram_weight=240
        )

        self.assertTrue(recipe.has_complete_nutrition_data())

        # Add ingredient without gram weight
        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=self.ingredient2,
            amount=Decimal('1'),
            unit='serving'
            # No gram_weight
        )

        self.assertFalse(recipe.has_complete_nutrition_data())

    def test_recipe_difficulty_choices(self):
        """Test difficulty level choices."""
        easy = Recipe.objects.create(
            title='Easy Recipe',
            author=self.user,
            instructions='Simple',
            difficulty='easy'
        )

        medium = Recipe.objects.create(
            title='Medium Recipe',
            author=self.user,
            instructions='Moderate',
            difficulty='medium'
        )

        hard = Recipe.objects.create(
            title='Hard Recipe',
            author=self.user,
            instructions='Complex',
            difficulty='hard'
        )

        self.assertEqual(easy.difficulty, 'easy')
        self.assertEqual(medium.difficulty, 'medium')
        self.assertEqual(hard.difficulty, 'hard')

    def test_recipe_placeholder_color_default(self):
        """Test default placeholder color."""
        recipe = Recipe.objects.create(
            title='Test Recipe',
            author=self.user,
            instructions='Instructions'
        )

        self.assertEqual(recipe.placeholder_color, '#0B63F2')

    def test_recipe_updated_date(self):
        """Test that updated_date is automatically set."""
        recipe = Recipe.objects.create(
            title='Test Recipe',
            author=self.user,
            instructions='Instructions'
        )

        original_updated = recipe.updated_date

        recipe.title = 'Updated Title'
        recipe.save()

        self.assertIsNotNone(recipe.updated_date)
        # Updated date should be same or later
        self.assertGreaterEqual(recipe.updated_date, original_updated)


class RecipeIngredientModelTest(TestCase):
    """Test cases for RecipeIngredient through model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        Profile.objects.filter(user=self.user).delete()

        self.ingredient = Ingredient.objects.create(
            name='Flour',
            brand='Generic',
            calories=364,  # per 100g
            nutrition_data={
                'macronutrients': {
                    'protein': {'name': 'Protein', 'amount': 10, 'unit': 'g'}
                },
                'vitamins': {},
                'minerals': {},
                'other': {}
            },
            portion_data=[
                {
                    'amount': 1,
                    'measure_unit': 'cup',
                    'gram_weight': 120
                }
            ]
        )

        self.recipe = Recipe.objects.create(
            title='Test Recipe',
            author=self.user,
            instructions='Mix and bake',
            servings=4
        )

    def test_recipe_ingredient_creation(self):
        """Test creating a recipe ingredient with amount and unit."""
        recipe_ing = RecipeIngredient.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            amount=Decimal('2.0'),
            unit='cup',
            gram_weight=240
        )

        self.assertIsNotNone(recipe_ing.pk)
        self.assertEqual(recipe_ing.amount, Decimal('2.0'))
        self.assertEqual(recipe_ing.unit, 'cup')
        self.assertEqual(recipe_ing.gram_weight, 240)

    def test_recipe_ingredient_str_representation(self):
        """Test string representation of recipe ingredient."""
        recipe_ing = RecipeIngredient.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            amount=Decimal('1.5'),
            unit='cup'
        )

        self.assertEqual(str(recipe_ing), '1.5 cup Flour')

    def test_recipe_ingredient_calculate_calories(self):
        """Test calorie calculation for recipe ingredient."""
        recipe_ing = RecipeIngredient.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            amount=Decimal('2.0'),
            unit='cup',
            gram_weight=240
        )

        # 364 cal/100g * 240g / 100 = 873.6 → 873 cal
        calories = recipe_ing.calculate_calories()
        self.assertEqual(calories, 873)

    def test_recipe_ingredient_calculate_calories_no_gram_weight(self):
        """Test calorie calculation returns 0 when gram_weight is None."""
        recipe_ing = RecipeIngredient.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            amount=Decimal('1.0'),
            unit='serving'
            # No gram_weight
        )

        calories = recipe_ing.calculate_calories()
        self.assertEqual(calories, 0)

    def test_recipe_ingredient_get_portion_gram_weight(self):
        """Test getting gram weight from USDA portion data."""
        recipe_ing = RecipeIngredient.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            amount=Decimal('2.0'),
            unit='cup'
        )

        gram_weight = recipe_ing.get_portion_gram_weight()
        self.assertEqual(gram_weight, 240)  # 2 cups * 120g per cup

    def test_recipe_ingredient_get_portion_gram_weight_no_data(self):
        """Test getting gram weight when ingredient has no portion data."""
        ingredient_no_portions = Ingredient.objects.create(
            name='Custom Item',
            calories=100
        )

        recipe_ing = RecipeIngredient.objects.create(
            recipe=self.recipe,
            ingredient=ingredient_no_portions,
            amount=Decimal('1.0'),
            unit='serving'
        )

        gram_weight = recipe_ing.get_portion_gram_weight()
        self.assertIsNone(gram_weight)

    def test_recipe_ingredient_auto_calculate_gram_weight(self):
        """Test automatic gram weight calculation."""
        recipe_ing = RecipeIngredient.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            amount=Decimal('2.0'),
            unit='cup'
        )

        success = recipe_ing.auto_calculate_gram_weight()
        self.assertTrue(success)
        self.assertEqual(recipe_ing.gram_weight, 240)

    def test_recipe_ingredient_unique_together_constraint(self):
        """Test that recipe-ingredient combination must be unique."""
        RecipeIngredient.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            amount=Decimal('1.0'),
            unit='cup'
        )

        with self.assertRaises(IntegrityError):
            RecipeIngredient.objects.create(
                recipe=self.recipe,
                ingredient=self.ingredient,
                amount=Decimal('2.0'),
                unit='cup'
            )

    def test_recipe_ingredient_ordering(self):
        """Test that recipe ingredients are ordered by order field."""
        ing2 = Ingredient.objects.create(name='Sugar', calories=387)

        recipe_ing1 = RecipeIngredient.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            amount=Decimal('1.0'),
            unit='cup',
            order=2
        )

        recipe_ing2 = RecipeIngredient.objects.create(
            recipe=self.recipe,
            ingredient=ing2,
            amount=Decimal('0.5'),
            unit='cup',
            order=1
        )

        ingredients = list(self.recipe.recipe_ingredients.all())
        self.assertEqual(ingredients[0], recipe_ing2)  # order=1 comes first
        self.assertEqual(ingredients[1], recipe_ing1)  # order=2 comes second

    def test_recipe_ingredient_notes_field(self):
        """Test optional notes field on recipe ingredient."""
        recipe_ing = RecipeIngredient.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            amount=Decimal('1.0'),
            unit='cup',
            notes='finely chopped'
        )

        self.assertEqual(recipe_ing.notes, 'finely chopped')

    def test_recipe_ingredient_decimal_amounts(self):
        """Test that decimal amounts are supported."""
        recipe_ing = RecipeIngredient.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            amount=Decimal('0.25'),
            unit='tsp'
        )

        self.assertEqual(recipe_ing.amount, Decimal('0.25'))


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
        RecipeIngredient.objects.create(
            recipe=unsafe_recipe,
            ingredient=ingredient,
            amount=1.0,
            unit='serving'
        )

        # Create safe recipe
        safe_ingredient = Ingredient.objects.create(name="Rice", calories=130)
        safe_recipe = Recipe.objects.create(
            title="Safe Recipe",
            author=self.user,
            instructions="No allergens"
        )
        RecipeIngredient.objects.create(
            recipe=safe_recipe,
            ingredient=safe_ingredient,
            amount=1.0,
            unit='serving'
        )

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
        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=self.ingredient,
            amount=1.0,
            unit='serving'
        )

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
        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=branded_ingredient,
            amount=1.0,
            unit='serving'
        )

        self.assertIn(branded_ingredient, recipe.ingredients.all())
        self.assertEqual(str(branded_ingredient), "Peanut Butter (Jif)")


class IngredientUSDAFieldsTestCase(TestCase):
    def test_has_nutrition_and_portion_flags(self):
        ing = Ingredient.objects.create(
            name="Test Food",
            brand="Generic",
            calories=100,
            nutrition_data={},
            portion_data=[],
        )
        self.assertFalse(ing.has_nutrition_data())
        self.assertFalse(ing.has_portion_data())

        ing.nutrition_data = {"macronutrients": {"protein": {"value": 10}}}
        ing.portion_data = [{"measure_unit": "cup", "gramweight": 240}]
        ing.save()

        self.assertTrue(ing.has_nutrition_data())
        self.assertTrue(ing.has_portion_data())

    def test_get_nutrient_by_category_and_key(self):
        ing = Ingredient.objects.create(
            name="Test Food",
            brand="Generic",
            calories=100,
            nutrition_data={
                "macronutrients": {
                    "protein": {"value": 8, "unit": "g"},
                },
                "vitamins": {
                    "vitaminc": {"value": 60, "unit": "mg"},
                },
            },
        )
        protein = ing.get_nutrient("protein", category="macronutrients")
        vitamin_c = ing.get_nutrient("vitaminc", category="vitamins")
        missing = ing.get_nutrient("fiber", category="macronutrients")

        self.assertEqual(protein["value"], 8)
        self.assertEqual(vitamin_c["value"], 60)
        self.assertIsNone(missing)

    def test_get_portion_by_unit(self):
        ing = Ingredient.objects.create(
            name="Bread",
            brand="Generic",
            calories=250,
            portion_data=[
                {"measure_unit": "slice", "gramweight": 30},
                {"measure_unit": "cup", "gramweight": 120},
            ],
        )
        slice_portion = ing.get_portion_by_unit("slice")
        cup_portion = ing.get_portion_by_unit("Cup")  # case-insensitive
        missing = ing.get_portion_by_unit("tablespoon")

        self.assertEqual(slice_portion["gramweight"], 30)
        self.assertEqual(cup_portion["gramweight"], 120)
        self.assertIsNone(missing)

    def test_is_usda_sourced_flag(self):
        ing_no_fdc = Ingredient.objects.create(
            name="Homemade Item",
            brand="Generic",
            calories=100,
        )
        ing_with_fdc = Ingredient.objects.create(
            name="USDA Item",
            brand="Brand",
            calories=50,
            fdc_id=123456,
        )
        self.assertFalse(ing_no_fdc.is_usda_sourced())
        self.assertTrue(ing_with_fdc.is_usda_sourced())
