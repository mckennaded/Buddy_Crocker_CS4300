"""
Views for Buddy Crocker meal planning and recipe management app.

Defines all HTTP request handlers and page rendering logic.
"""

import os
import sys
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST, require_http_methods

from openai import OpenAI

from services import usda_api
from .forms import (
    CustomUserCreationForm,
    IngredientForm,
    ProfileForm,
    RecipeForm,
    UserForm,
    AIRecipeForm,
)
from .models import Allergen, Ingredient, Pantry, Profile, Recipe

User = get_user_model()


def _get_pantry_ingredient_names(user):
    pantry_obj, _ = Pantry.objects.get_or_create(user=user)  # pylint: disable=no-member
    return [ingredient.name for ingredient in pantry_obj.ingredients.all()]  # pylint: disable=no-member


def _get_user_allergen_names(user):
    try:
        return [a.name for a in user.profile.allergens.all()]  # pylint: disable=no-member
    except Profile.DoesNotExist:  # pylint: disable=no-member
        return []


def _parse_ai_response(ai_text):
    recipes = []
    blocks = re.split(r"(?=Title: )", ai_text.strip())
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        title, ingredients, instructions = "", [], []
        lines = block.split("\n")
        mode = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.lower().startswith("title:"):
                title = line.replace("Title:", "").strip()
                continue
            if line.lower().startswith("ingredients:"):
                mode = "ingredients"
                continue
            if line.lower().startswith("instructions:"):
                mode = "instructions"
                continue
            if mode == "ingredients":
                ingredients.append(line.lstrip("- ").strip())
            elif mode == "instructions":
                instructions.append(line)
        if title:
            recipes.append(
                {
                    "title": title,
                    "ingredients": ingredients,
                    "instructions": "\n".join(instructions),
                }
            )
    return recipes


def _match_ingredients_to_form(recipes):
    forms = []
    for r in recipes:
        all_db_ingredients = list(Ingredient.objects.all())  # pylint: disable=no-member
        input_names = [i.strip().lower() for i in r["ingredients"] if i]
        matched_ingredients = [
            ing for ing in all_db_ingredients if ing.name.strip().lower() in input_names
        ]
        forms.append(
            AIRecipeForm(
                initial={
                    "title": r["title"],
                    "instructions": r["instructions"],
                    "ingredients": [ing.pk for ing in matched_ingredients],
                }
            )
        )
    return forms


@login_required
@require_http_methods(["GET", "POST"])
def recipe_generator(request):
    """
    Generate recipes using AI based on pantry ingredients and allergens.

    Handles:
    - POST "generate_recipes": calls OpenAI API to generate recipes.
    - POST "save_recipe": saves the submitted recipe form.
    - GET: renders the form.
    """
    ingredient_names = _get_pantry_ingredient_names(request.user)
    preferences = _get_user_allergen_names(request.user)

    recipes = []
    error_msg = None
    forms = []

    if request.method == "POST":
        if "generate_recipes" in request.POST and ingredient_names:
            try:
                api_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAPI_KEY", None)
                if not api_key:
                    raise ValueError("OpenAI API key not found")

                client = OpenAI(api_key=api_key)
                prompt = (
                    "Generate 2 concise recipe ideas using only these ingredients: "
                    f"{', '.join(ingredient_names)}. "
                    "Avoid these allergens: "
                    f"{', '.join(preferences)}. "
                    "For each recipe, group as follows:\nTitle: <Recipe title>\n"
                    "Ingredients:\n- <ingredient 1>\n- <ingredient 2>\n"
                    "Instructions:\n1. <step 1>\n2. <step 2>\n"
                    "Do not use markdown or extra formatting."
                )
                response = client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful cooking assistant."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                )
                ai_text = response.choices[0].message.content
                recipes = _parse_ai_response(ai_text)
                forms = _match_ingredients_to_form(recipes)
            except ValueError as ve:
                error_msg = f"API key error: {ve}"
            except Exception as e:  # pylint: disable=broad-except
                error_msg = f"API call or parsing failed: {e}"

        elif "save_recipe" in request.POST:
            form = AIRecipeForm(request.POST)
            if form.is_valid():
                recipe = form.save(commit=False)
                recipe.author = request.user
                recipe.save()
                form.save_m2m()
                messages.success(request, f"Recipe '{recipe.title}' added to your profile!")
                return redirect("profile-detail", pk=request.user.pk)
            error_msg = "Please correct the errors below."
            recipes = []
            forms = [form]

    if not forms:
        forms = [AIRecipeForm()]

    zipped = list(zip(recipes, forms))
    context = {
        "ingredient_names": ingredient_names,
        "recipes": recipes,
        "error_msg": error_msg,
        "forms": forms,
        "zipped_recipes_forms": zipped,
    }
    return render(request, "buddy_crocker/recipe_generator.html", context)


@require_POST
@login_required
def custom_logout(request):
    """Log out the current user and redirect to login page."""
    logout(request)
    return redirect("login")


class CustomLoginView(LoginView):
    """Custom Django login view redirecting to profile detail."""

    def get_success_url(self):
        return reverse("profile-detail", kwargs={"pk": self.request.user.pk})


@login_required
def register(request):
    """
    Handle user registration with automatic login after signup.
    """
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect("profile-detail", pk=user.pk)
    else:
        form = CustomUserCreationForm()
    return render(request, "registration/register.html", {"form": form})


def index(request):
    """
    Render the home page with featured recipes.
    """
    recent_recipes = Recipe.objects.all()[:6]  # pylint: disable=no-member
    context = {"recent_recipes": recent_recipes}
    return render(request, "buddy_crocker/index.html", context)


def _get_user_allergen_info(request):
    """
    Helper function to fetch user's allergens and their IDs.
    """
    user_allergens = []
    user_profile_allergen_ids = []
    if request.user.is_authenticated:
        try:
            profile = request.user.profile  # pylint: disable=no-member
            user_allergens = list(profile.allergens.all())  # pylint: disable=no-member
            user_profile_allergen_ids = [a.id for a in user_allergens]
        except Profile.DoesNotExist:  # pylint: disable=no-member
            pass
    return user_allergens, user_profile_allergen_ids


def _filter_recipes_by_allergens(recipes, exclude_allergen_ids):
    """
    Filter recipes containing specified allergens.
    """
    recipes_with_allergens = Recipe.objects.filter(
        ingredients__allergens__id__in=exclude_allergen_ids  # pylint: disable=no-member
    ).distinct()
    return recipes.exclude(id__in=recipes_with_allergens)


def recipe_search(request):
    """
    Display recipe search page with filters and pagination.
    """
    recipes = Recipe.objects.all().select_related("author").prefetch_related("ingredients")  # pylint: disable=no-member
    search_query = request.GET.get("q", "")
    if search_query:
        recipes = recipes.filter(title__icontains=search_query)
    exclude_allergens = request.GET.getlist("exclude_allergens")
    if exclude_allergens:
        recipes = _filter_recipes_by_allergens(
            recipes, [int(aid) for aid in exclude_allergens if aid.isdigit()]
        )
    all_allergens = Allergen.objects.all()  # pylint: disable=no-member
    user_allergens, user_profile_allergen_ids = _get_user_allergen_info(request)
    if exclude_allergens:
        selected_allergen_ids = [int(aid) for aid in exclude_allergens if aid.isdigit()]
    else:
        selected_allergen_ids = user_profile_allergen_ids
    recipes_with_info = []
    for recipe in recipes:
        recipe.ingredient_count = recipe.ingredients.count()
        if request.user.is_authenticated and user_allergens:
            recipe_allergens = recipe.get_allergens()
            recipe.is_safe_for_user = not any(allergen in user_allergens for allergen in recipe_allergens)
        else:
            recipe.is_safe_for_user = None
        recipes_with_info.append(recipe)
    paginator = Paginator(recipes_with_info, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    context = {
        "page_obj": page_obj,
        "recipes": page_obj,
        "all_allergens": all_allergens,
        "selected_allergen_ids": selected_allergen_ids,
        "user_profile_allergen_ids": user_profile_allergen_ids,
        "search_query": search_query,
        "total_count": paginator.count,
    }
    return render(request, "buddy_crocker/recipe-search.html", context)


def _get_allergen_context(all_allergens, user_allergens):
    """
    Determine allergen display context based on user profile.
    """
    relevant_allergens = []
    has_allergen_conflict = False
    is_safe_for_user = False
    show_all_allergens = True
    if user_allergens:
        show_all_allergens = False
        relevant_allergens = [a for a in all_allergens if a in user_allergens]
        has_allergen_conflict = len(relevant_allergens) > 0
        is_safe_for_user = len(relevant_allergens) == 0
    elif user_allergens is not None:
        show_all_allergens = False
        is_safe_for_user = True
    return {
        "relevant_allergens": relevant_allergens,
        "has_allergen_conflict": has_allergen_conflict,
        "is_safe_for_user": is_safe_for_user,
        "show_all_allergens": show_all_allergens,
    }


def recipe_detail(request, pk):
    """
    Display details of a recipe with personalized allergen warnings.
    """
    recipe = get_object_or_404(Recipe, pk=pk)  # pylint: disable=no-member
    ingredients = recipe.ingredients.all()
    all_recipe_allergens = recipe.get_allergens()
    user_allergens = None
    if request.user.is_authenticated:
        try:
            profile = request.user.profile  # pylint: disable=no-member
            user_allergens = list(profile.allergens.all())  # pylint: disable=no-member
        except Profile.DoesNotExist:  # pylint: disable=no-member
            pass
    allergen_ctx = _get_allergen_context(all_recipe_allergens, user_allergens)
    context = {
        "recipe": recipe,
        "ingredients": ingredients,
        "all_recipe_allergens": all_recipe_allergens,
        "user_allergens": user_allergens or [],
        **allergen_ctx,
    }
    return render(request, "buddy_crocker/recipe_detail.html", context)


def ingredient_detail(request, pk):
    """
    Display details of an ingredient with allergen warnings.
    """
    ingredient = get_object_or_404(Ingredient, pk=pk)  # pylint: disable=no-member
    all_allergens = ingredient.allergens.all()
    related_recipes = ingredient.recipes.all()
    user_allergens = None
    if request.user.is_authenticated:
        try:
            profile = request.user.profile  # pylint: disable=no-member
            user_allergens = list(profile.allergens.all())  # pylint: disable=no-member
        except Profile.DoesNotExist:  # pylint: disable=no-member
            pass
    allergen_ctx = _get_allergen_context(all_allergens, user_allergens)
    context = {
        "ingredient": ingredient,
        "all_allergens": all_allergens,
        "user_allergens": user_allergens or [],
        "related_recipes": related_recipes,
        **allergen_ctx,
    }
    return render(request, "buddy_crocker/ingredient_detail.html", context)


def allergen_detail(request, pk):
    """
    Display details of an allergen and recipes/ingredients affected.
    """
    allergen = get_object_or_404(Allergen, pk=pk)  # pylint: disable=no-member
    affected_ingredients = allergen.ingredients.all()
    affected_recipes = Recipe.objects.filter(ingredients__allergens=allergen).distinct()  # pylint: disable=no-member
    can_add_to_profile = False
    already_in_profile = False
    if request.user.is_authenticated:
        try:
            profile = request.user.profile  # pylint: disable=no-member
            already_in_profile = allergen in profile.allergens.all()  # pylint: disable=no-member
            can_add_to_profile = not already_in_profile
        except Profile.DoesNotExist:  # pylint: disable=no-member
            pass
    context = {
        "allergen": allergen,
        "affected_ingredients": affected_ingredients,
        "affected_recipes": affected_recipes,
        "can_add_to_profile": can_add_to_profile,
        "already_in_profile": already_in_profile,
    }
    return render(request, "buddy_crocker/allergen_detail.html", context)


def _categorize_pantry_ingredients(pantry_ingredients, user_allergens):
    """
    Categorize pantry ingredients as safe or unsafe based on user allergens.
    """
    safe_ingredients = []
    unsafe_ingredients = []
    for ingredient in pantry_ingredients:
        ingredient_allergens = list(ingredient.allergens.all())
        relevant_allergens = [a for a in ingredient_allergens if a in user_allergens]
        ingredient.relevant_allergens = relevant_allergens
        ingredient.has_conflict = len(relevant_allergens) > 0
        ingredient.is_safe = len(relevant_allergens) == 0
        if ingredient.has_conflict:
            unsafe_ingredients.append(ingredient)
        else:
            safe_ingredients.append(ingredient)
    return safe_ingredients, unsafe_ingredients


@login_required
def pantry(request):
    """
    View and manage user's pantry with allergen warnings.
    """
    pantry_obj, _created = Pantry.objects.get_or_create(user=request.user)  # pylint: disable=no-member
    if request.method == "POST":
        action = request.POST.get("action")
        ingredient_id = request.POST.get("ingredient_id")
        if ingredient_id:
            ingredient = get_object_or_404(Ingredient, pk=ingredient_id)  # pylint: disable=no-member
            if action == "add":
                pantry_obj.ingredients.add(ingredient)  # pylint: disable=no-member
            elif action == "remove":
                pantry_obj.ingredients.remove(ingredient)  # pylint: disable=no-member
        return redirect("pantry")
    pantry_ingredients = pantry_obj.ingredients.all().prefetch_related("allergens")  # pylint: disable=no-member
    user_allergens = []
    show_allergen_warnings = False
    try:
        profile = request.user.profile  # pylint: disable=no-member
        user_allergens = list(profile.allergens.all())  # pylint: disable=no-member
        show_allergen_warnings = bool(user_allergens)
    except Profile.DoesNotExist:  # pylint: disable=no-member
        pass
    if user_allergens:
        safe_ingredients, unsafe_ingredients = _categorize_pantry_ingredients(pantry_ingredients, user_allergens)
    else:
        safe_ingredients = []
        unsafe_ingredients = []
        for ingredient in pantry_ingredients:
            ingredient.relevant_allergens = []
            ingredient.has_conflict = False
            ingredient.is_safe = True
            safe_ingredients.append(ingredient)
    all_ingredients = Ingredient.objects.all()  # pylint: disable=no-member
    pantry_ingredient_ids = set(pantry_obj.ingredients.values_list("id", flat=True))  # pylint: disable=no-member
    context = {
        "pantry": pantry_obj,
        "safe_ingredients": safe_ingredients,
        "unsafe_ingredients": unsafe_ingredients,
        "user_allergens": user_allergens,
        "show_allergen_warnings": show_allergen_warnings,
        "total_ingredients": pantry_ingredients.count(),
        "unsafe_count": len(unsafe_ingredients),
        "safe_count": len(safe_ingredients),
        "all_ingredients": all_ingredients,
        "pantry_ingredient_ids": pantry_ingredient_ids,
    }
    return render(request, "buddy_crocker/pantry.html", context)


@login_required
def add_ingredient(request):
    """
    Create a new ingredient.
    """
    if request.method == "POST":
        form = IngredientForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"]
            calories = form.cleaned_data["calories"]
            allergens = form.cleaned_data["allergens"]
            brand = form.cleaned_data["brand"]
            ingredient, created = Ingredient.objects.get_or_create(  # pylint: disable=no-member
                name=name,
                brand=brand,
                defaults={"calories": calories},
            )
            if not created and ingredient.calories != calories:
                ingredient.calories = calories
                ingredient.save()
            ingredient.allergens.set(allergens)
            if request.user.is_authenticated:
                user_pantry, _created = Pantry.objects.get_or_create(user=request.user)  # pylint: disable=no-member
                if ingredient not in user_pantry.ingredients.all():  # pylint: disable=no-member
                    user_pantry.ingredients.add(ingredient)  # pylint: disable=no-member
            return redirect("ingredient-detail", pk=ingredient.pk)
        messages.error(request, "Please fix the errors below before submitting.")
    else:
        form = IngredientForm()
    return render(request, "buddy_crocker/add-ingredient.html", {"form": form})


@login_required
def add_recipe(request):
    """
    Display form to add a new recipe and handle submission.
    """
    if request.method == "POST":
        form = RecipeForm(request.POST)
        if form.is_valid():
            title = (form.cleaned_data.get("title") or "").strip()
            if Recipe.objects.filter(author=request.user, title__iexact=title).exists():  # pylint: disable=no-member
                form.add_error(
                    "title",
                    "You already have a recipe with this title. Choose a different title.",
                )
                messages.error(request, "Please correct the errors below.")
                return render(request, "buddy_crocker/add_recipe.html", {"form": form})
            recipe = form.save(commit=False)
            recipe.author = request.user
            recipe.title = title
            try:
                recipe.save()
                form.save_m2m()
                messages.success(request, "Recipe added successfully!")
                return redirect("recipe-detail", pk=recipe.pk)
            except IntegrityError:
                form.add_error(
                    "title",
                    "You already have a recipe with this title. Choose a different title.",
                )
                messages.error(
                    request, "There was a problem saving your recipe. Please try again."
                )
                return render(request, "buddy_crocker/add_recipe.html", {"form": form})
        messages.error(request, "Please fix the errors below.")
    else:
        form = RecipeForm()
    return render(request, "buddy_crocker/add_recipe.html", {"form": form})


@login_required
def profile_detail(request, pk):
    """
    Display and edit user profile.
    """
    if request.user.pk != pk:
        return redirect("profile-detail", pk=request.user.pk)
    user = get_object_or_404(User, pk=pk)
    profile, _created = Profile.objects.get_or_create(user=user)  # pylint: disable=no-member
    user_pantry, _ = Pantry.objects.get_or_create(user=user)  # pylint: disable=no-member
    pantry_ingredient_ids = set(user_pantry.ingredients.values_list("id", flat=True))  # pylint: disable=no-member
    safe_recipes = profile.get_safe_recipes()  # pylint: disable=no-member
    recipes_you_can_make = []
    for recipe in safe_recipes:
        recipe_ingredient_ids = set(recipe.ingredients.values_list("id", flat=True))  # pylint: disable=no-member
        if recipe_ingredient_ids.issubset(pantry_ingredient_ids):
            recipes_you_can_make.append(recipe)
    edit_mode = request.GET.get("edit") == "1"
    if request.method == "POST":
        user_form = UserForm(request.POST, instance=user)
        profile_form = ProfileForm(request.POST, instance=profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            return redirect("profile-detail", pk=pk)
    else:
        user_form = UserForm(instance=user)
        profile_form = ProfileForm(instance=profile)
    context = {
        "user_form": user_form,
        "profile_form": profile_form,
        "user": user,
        "profile": profile,
        "pantry": user_pantry,
        "recipes_you_can_make": recipes_you_can_make,
        "edit_mode": edit_mode,
        "safe_recipe_count": safe_recipes.count(),
        "total_recipe_count": Recipe.objects.count(),  # pylint: disable=no-member
    }
    return render(request, "buddy_crocker/profile_detail.html", context)


def preview_404(request):
    """Render 404 error page"""
    return render(request, "buddy_crocker/404.html", status=404)


def preview_500(request):
    """Render 500 error page"""
    return render(request, "buddy_crocker/500.html", status=500)


def page_not_found_view(request, exception=None, template_name="buddy_crocker/404.html"):  # pylint: disable=unused-argument
    """Render 404 error page"""
    return render(request, template_name, status=404)


def server_error_view(request, exception=None, template_name="buddy_crocker/500.html"):  # pylint: disable=unused-argument
    """Render 500 error page"""
    return render(request, template_name, status=500)


@require_http_methods(["GET"])
def search_usda_ingredients(request):
    """
    AJAX endpoint to search USDA database for ingredients with allergen detection.
    """
    query = request.GET.get("q", "").strip()
    if not query or len(query) < 2:
        return JsonResponse({"results": []})
    current_dir = os.path.dirname(os.path.abspath(__file__))
    services_dir = os.path.join(current_dir, "..", "services")
    if services_dir not in sys.path:
        sys.path.insert(0, services_dir)
    try:
        foods = usda_api.search_foods(query, page_size=10, use_cache=True)
        all_allergens = Allergen.objects.all()  # pylint: disable=no-member
        results = []
        for food in foods:
            name = food.get("description", "")
            brand = food.get("brandOwner", "") or "Generic"
            calories = next(
                (
                    nutrient.get("value", 0)
                    for nutrient in food.get("foodNutrients", [])
                    if nutrient.get("nutrientName") == "Energy"
                ),
                0,
            )
            detected_allergens = detect_allergens_from_name(name, all_allergens)
            results.append(
                {
                    "name": name,
                    "brand": brand,
                    "calories": int(calories) if calories else 0,
                    "fdc_id": food.get("fdcId", ""),
                    "data_type": food.get("dataType", ""),
                    "suggested_allergens": [
                        {
                            "id": allergen.id,
                            "name": allergen.name,
                            "category": allergen.category,
                        }
                        for allergen in detected_allergens
                    ],
                }
            )
        return JsonResponse({"results": results})
    except ImportError as e:
        return JsonResponse(
            {"error": f"USDA API module not available: {str(e)}"}, status=500
        )
    except (ValueError, KeyError, TypeError) as e:
        return JsonResponse(
            {"error": f"Failed to search USDA database: {str(e)}"}, status=500
        )
    except Exception as e:  # pylint: disable=broad-except
        return JsonResponse(
            {"error": f"Failed to search USDA database: {str(e)}"}, status=500
        )


def detect_allergens_from_name(ingredient_name, allergen_objects):
    """
    Detect potential allergens in an ingredient name via string matching.
    """
    ingredient_lower = ingredient_name.lower()
    detected_allergens = []
    for allergen in allergen_objects:
        if allergen.name.lower() in ingredient_lower:
            if allergen not in detected_allergens:
                detected_allergens.append(allergen)
            continue
        for alt_name in allergen.alternative_names:
            if alt_name.lower() in ingredient_lower:
                if allergen not in detected_allergens:
                    detected_allergens.append(allergen)
                break
    return detected_allergens
