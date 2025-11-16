from django.contrib.auth.models import User
from buddy_crocker.models import Recipe, Ingredient
from buddy_crocker.forms import RecipeForm, IngredientForm

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

class TestRecipeForm:
    def test_blank_fields_invalid(self, django_user_model):
        user = django_user_model.objects.create_user(username="a", password="x")
        form = RecipeForm(data={"title": "", "instructions": ""}, user=user)
        assert not form.is_valid()
        assert "Please enter a title for your recipe." in form.errors["title"][0]
        assert "Write a few steps so people can make it." in form.errors["instructions"][0]

    def test_instructions_min_length(self, django_user_model):
        user = django_user_model.objects.create_user(username="b", password="x")
        form = RecipeForm(data={"title": "Shorty", "instructions": "too short"}, user=user)
        assert not form.is_valid()
        assert "Instructions are a bit short" in form.errors["instructions"][0]

    def test_duplicate_title_per_author(self, django_user_model):
        user = django_user_model.objects.create_user(username="c", password="x")
        Recipe.objects.create(title="Tacos", author=user, instructions="long enough text")
        form = RecipeForm(data={"title": "tacos", "instructions": "long enough text"}, user=user)
        assert not form.is_valid()
        assert "already have a recipe with that title" in form.errors["title"][0]

    def test_valid_recipe(self, django_user_model):
        user = django_user_model.objects.create_user(username="d", password="x")
        form = RecipeForm(data={"title": "Lasagna", "instructions": "Lots of steps here..."}, user=user)
        assert form.is_valid()
        recipe = form.save(commit=False)
        recipe.author = user
        recipe.save()
        assert recipe.pk
