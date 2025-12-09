"""Views for Buddy Crocker meal planning and recipe management app."""
import json
import logging

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST, require_http_methods

from services import usda_api
from services import usda_service
from services.allergen_service import (
    get_user_allergens,
    get_allergen_context,
    categorize_pantry_ingredients,
)
from services.recipe_service import filter_recipes_by_allergens
from services.scan_service import process_pantry_scan, add_ingredients_to_pantry
from .ai_recipe_service import generate_ai_recipes
from .forms import (
    CustomUserCreationForm,
    IngredientForm,
    ProfileForm,
    RecipeForm,
    RecipeIngredientFormSet,
    SaveAIRecipeForm,
    UserForm,
    ShoppingListItemForm,
)
from .models import (
     Allergen, 
     Ingredient, 
     Pantry, 
     Profile, 
     Recipe, 
     RecipeIngredient, 
     ShoppingListItem
)

User = get_user_model()

logger = logging.getLogger(__name__)


@require_POST
@login_required
def custom_logout(request):
    """Log out the current user and redirect to login page."""
    logout(request)
    return redirect("login")


class CustomLoginView(LoginView):
    """Custom Django login view with profile-based redirect."""

    def get_success_url(self):
        """Redirect to user's profile detail page after login."""
        return reverse("profile-detail", kwargs={"pk": self.request.user.pk})


def register(request):
    """Handle user registration with automatic login after signup."""
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
    """Render the home page with featured recipes."""
    recent_recipes = Recipe.objects.all()[:6]
    context = {"recent_recipes": recent_recipes}
    return render(request, "buddy_crocker/index.html", context)


def recipe_search(request):
    """Display recipe search/browse page with optional filtering."""
    recipes = Recipe.objects.all().select_related("author").prefetch_related(
        "ingredients",
    )

    # Search by title
    search_query = request.GET.get("q", "")
    if search_query:
        recipes = recipes.filter(title__icontains=search_query)

    # Get user allergen info
    user_allergens, user_profile_allergen_ids = get_user_allergens(request.user)

    # Filter by allergens
    exclude_allergens = request.GET.getlist("exclude_allergens")
    if exclude_allergens:
        allergen_ids = [int(aid) for aid in exclude_allergens if aid.isdigit()]
        recipes = filter_recipes_by_allergens(recipes, allergen_ids)
        selected_allergen_ids = allergen_ids
    else:
        selected_allergen_ids = user_profile_allergen_ids

    # Add metadata to recipes
    for recipe in recipes:
        recipe.ingredient_count = recipe.ingredients.count()
        if request.user.is_authenticated and user_allergens:
            recipe_allergens = recipe.get_allergens()
            recipe.is_safe_for_user = not any(
                allergen in user_allergens for allergen in recipe_allergens
            )
        else:
            recipe.is_safe_for_user = None

    # Pagination
    paginator = Paginator(recipes, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "recipes": page_obj,
        "all_allergens": Allergen.objects.all(),
        "selected_allergen_ids": selected_allergen_ids,
        "user_profile_allergen_ids": user_profile_allergen_ids,
        "search_query": search_query,
        "total_count": paginator.count,
    }
    return render(request, "buddy_crocker/recipe-search.html", context)


def recipe_detail(request, pk):
    """Display recipe with calculated nutrition information."""
    recipe = get_object_or_404(Recipe, pk=pk)

    # Get ingredients with amounts
    recipe_ingredients = recipe.get_ingredient_list()

    # Calculate nutrition
    total_calories = recipe.calculate_total_calories()
    calories_per_serving = recipe.calculate_calories_per_serving()
    has_complete_nutrition = recipe.has_complete_nutrition_data()

    # Calculate gram weight
    for recipe_ing in recipe_ingredients:
        if not recipe_ing.gram_weight:
            recipe_ing.auto_calculate_gram_weight()
            if recipe_ing.gram_weight:
                recipe_ing.save()

    # Get total time
    total_time = recipe.get_total_time()

    # Allergen information
    all_recipe_allergens = recipe.get_allergens()

    # User-specific allergen checks
    user_allergens = []
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            user_allergens = list(profile.allergens.all())
        except Exception:  # pylint: disable=broad-exception-caught
            user_allergens = []

    # Determine allergen conflicts
    relevant_allergens = []
    has_allergen_conflict = False
    is_safe_for_user = False

    if user_allergens:
        relevant_allergens = [
            allergen for allergen in all_recipe_allergens if allergen in user_allergens
        ]
        has_allergen_conflict = len(relevant_allergens) > 0
        is_safe_for_user = len(relevant_allergens) == 0

    context = {
        "recipe": recipe,
        "recipe_ingredients": recipe_ingredients,
        "total_calories": total_calories,
        "calories_per_serving": calories_per_serving,
        "has_complete_nutrition": has_complete_nutrition,
        "total_time": total_time,
        "all_recipe_allergens": all_recipe_allergens,
        "user_allergens": user_allergens,
        "relevant_allergens": relevant_allergens,
        "has_allergen_conflict": has_allergen_conflict,
        "is_safe_for_user": is_safe_for_user,
    }
    return render(request, "buddy_crocker/recipe_detail.html", context)


def ingredient_detail(request, pk):
    """Display detailed information about a specific ingredient."""
    ingredient = get_object_or_404(Ingredient, pk=pk)
    all_allergens = ingredient.allergens.all()
    related_recipes = ingredient.recipes.all()

    user_allergens, _ = get_user_allergens(request.user)
    allergen_ctx = get_allergen_context(all_allergens, user_allergens)

    context = {
        "ingredient": ingredient,
        "all_allergens": all_allergens,
        "user_allergens": user_allergens or [],
        "related_recipes": related_recipes,
        **allergen_ctx,
    }
    return render(request, "buddy_crocker/ingredient_detail.html", context)


def allergen_detail(request, pk):
    """Display detailed information about a specific allergen."""
    allergen = get_object_or_404(Allergen, pk=pk)
    affected_ingredients = allergen.ingredients.all()
    affected_recipes = Recipe.objects.filter(
        ingredients__allergens=allergen,
    ).distinct()

    can_add_to_profile = False
    already_in_profile = False
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            already_in_profile = allergen in profile.allergens.all()
            can_add_to_profile = not already_in_profile
        except Profile.DoesNotExist:
            can_add_to_profile = False

    context = {
        "allergen": allergen,
        "affected_ingredients": affected_ingredients,
        "affected_recipes": affected_recipes,
        "can_add_to_profile": can_add_to_profile,
        "already_in_profile": already_in_profile,
    }
    return render(request, "buddy_crocker/allergen_detail.html", context)


@login_required
def pantry(request):
    """Display and manage the user's pantry with allergen warnings."""
    pantry_obj, _ = Pantry.objects.get_or_create(user=request.user)

    if request.method == "POST":
        action = request.POST.get("action")
        ingredient_id = request.POST.get("ingredient_id")

        if ingredient_id:
            ingredient = get_object_or_404(Ingredient, pk=ingredient_id)
            if action == "add":
                pantry_obj.ingredients.add(ingredient)
            elif action == "remove":
                pantry_obj.ingredients.remove(ingredient)
        return redirect("pantry")

    pantry_ingredients = pantry_obj.ingredients.all().prefetch_related("allergens")
    user_allergens, _ = get_user_allergens(request.user)
    show_allergen_warnings = bool(user_allergens)

    # Categorize ingredients
    safe_ingredients, unsafe_ingredients = categorize_pantry_ingredients(
        pantry_ingredients,
        user_allergens,
    )

    context = {
        "pantry": pantry_obj,
        "safe_ingredients": safe_ingredients,
        "unsafe_ingredients": unsafe_ingredients,
        "user_allergens": user_allergens,
        "show_allergen_warnings": show_allergen_warnings,
        "total_ingredients": pantry_ingredients.count(),
        "unsafe_count": len(unsafe_ingredients),
        "safe_count": len(safe_ingredients),
        "all_ingredients": Ingredient.objects.all(),
        "pantry_ingredient_ids": set(
            pantry_obj.ingredients.values_list("id", flat=True),
        ),
    }
    return render(request, "buddy_crocker/pantry.html", context)


@login_required
def add_ingredient(request):
    """Create a new ingredient with optional USDA nutrition data."""
    if request.method == "POST":
        form = IngredientForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"]
            calories = form.cleaned_data["calories"]
            allergens = form.cleaned_data["allergens"]
            brand = form.cleaned_data["brand"]

            # Get fdc_id if this came from USDA search
            fdc_id = request.POST.get("fdc_id", "").strip()
            fdc_id = int(fdc_id) if fdc_id else None

            complete_data = None
            if fdc_id:
                complete_data, should_abort, error_info = (
                    usda_service.fetch_usda_data_with_error_handling(
                        request,
                        fdc_id,
                        name,
                    )
                )

                if error_info:
                    getattr(messages, error_info["level"])(
                        request,
                        error_info["message"],
                    )

                if should_abort:
                    return render(
                        request,
                        "buddy_crocker/add-ingredient.html",
                        {"form": form},
                    )

            ingredient, created = Ingredient.objects.get_or_create(
                name=name,
                brand=brand,
                defaults={"calories": calories},
            )

            if not created and ingredient.calories != calories:
                ingredient.calories = calories

            if complete_data:
                ingredient.fdc_id = fdc_id
                ingredient.nutrition_data = complete_data["nutrients"]
                ingredient.portion_data = complete_data["portions"]
                if complete_data["basic"]["calories_per_100g"]:
                    ingredient.calories = int(
                        complete_data["basic"]["calories_per_100g"],
                    )

            ingredient.save()
            ingredient.allergens.set(allergens)

            if request.user.is_authenticated:
                user_pantry, _ = Pantry.objects.get_or_create(user=request.user)
                if ingredient not in user_pantry.ingredients.all():
                    user_pantry.ingredients.add(ingredient)

            messages.success(
                request,
                f"Successfully added {ingredient.name}!",
            )
            return redirect("ingredient-detail", pk=ingredient.pk)

        messages.error(request, "Please fix the errors below before submitting.")
    else:
        form = IngredientForm()

    return render(request, "buddy_crocker/add-ingredient.html", {"form": form})


@require_http_methods(["POST"])
@login_required
def quick_add_usda_ingredient(request):
    """Quick add ingredient from USDA to pantry and return ingredient data."""
    try:
        data = json.loads(request.body)
        name = data.get("name")
        brand = data.get("brand", "Generic")
        fdc_id = data.get("fdc_id")

        if not name or not fdc_id:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Missing required fields",
                },
                status=400,
            )

        complete_data, should_abort, error_info = (
            usda_service.fetch_usda_data_with_error_handling(
                request,
                int(fdc_id),
                name,
            )
        )

        if should_abort or not complete_data:
            return JsonResponse(
                {
                    "success": False,
                    "error": error_info.get(
                        "message",
                        "Failed to fetch ingredient data",
                    ),
                },
                status=400,
            )

        ingredient, _ = Ingredient.objects.get_or_create(
            name=name,
            brand=brand,
            defaults={
                "calories": int(
                    complete_data["basic"]["calories_per_100g"] or 0,
                ),
            },
        )

        ingredient.fdc_id = int(fdc_id)
        ingredient.nutrition_data = complete_data["nutrients"]
        ingredient.portion_data = complete_data["portions"]
        ingredient.calories = int(
            complete_data["basic"]["calories_per_100g"] or 0,
        )
        ingredient.save()

        pantry_obj, _ = Pantry.objects.get_or_create(user=request.user)
        pantry_obj.ingredients.add(ingredient)

        return JsonResponse(
            {
                "success": True,
                "ingredient": {
                    "id": ingredient.id,
                    "name": ingredient.name,
                    "brand": ingredient.brand,
                    "display_name": str(ingredient),
                    "calories": ingredient.calories,
                },
            },
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {
                "success": False,
                "error": "Invalid JSON data",
            },
            status=400,
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Error in quick_add_usda_ingredient: %s", str(exc))
        return JsonResponse(
            {
                "success": False,
                "error": f"Failed to add ingredient: {str(exc)}",
            },
            status=500,
        )


@login_required
@transaction.atomic
def add_recipe(request):
    """Create a new recipe with ingredients and amounts."""
    if request.method == "POST":
        form = RecipeForm(request.POST, request.FILES)
        formset = RecipeIngredientFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            recipe = form.save(commit=False)
            recipe.author = request.user
            recipe.save()

            formset.instance = recipe
            instances = formset.save(commit=False)

            for instance in instances:
                instance.auto_calculate_gram_weight()
                instance.save()

            for obj in formset.deleted_objects:
                obj.delete()

            messages.success(
                request,
                f'Recipe "{recipe.title}" created successfully!',
            )
            return redirect("recipe-detail", pk=recipe.pk)

        messages.error(request, "Please correct the errors below.")
    else:
        form = RecipeForm()
        formset = RecipeIngredientFormSet()

    try:
        pantry_obj = Pantry.objects.get(user=request.user)
        available_ingredients = pantry_obj.ingredients.all()
    except Pantry.DoesNotExist:
        available_ingredients = Ingredient.objects.none()

    context = {
        "form": form,
        "formset": formset,
        "available_ingredients": available_ingredients,
    }
    return render(request, "buddy_crocker/add_recipe.html", context)


@login_required
def profile_detail(request, pk):
    """Display and edit user profile."""
    if request.user.pk != pk:
        return redirect("profile-detail", pk=request.user.pk)

    user = get_object_or_404(User, pk=pk)
    profile, _ = Profile.objects.get_or_create(user=user)
    user_pantry, _ = Pantry.objects.get_or_create(user=user)
    pantry_ingredient_ids = set(
        user_pantry.ingredients.values_list("id", flat=True),
    )

    safe_recipes = profile.get_safe_recipes()
    recipes_you_can_make = [
        recipe
        for recipe in safe_recipes
        if set(recipe.ingredients.values_list("id", flat=True)).issubset(
            pantry_ingredient_ids,
        )
    ]

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
        "total_recipe_count": Recipe.objects.count(),
    }
    return render(request, "buddy_crocker/profile_detail.html", context)


def preview_404(request):
    """Display template for 404 page."""
    return render(request, "buddy_crocker/404.html", status=404)


def preview_500(request):
    """Display server error template."""
    return render(request, "buddy_crocker/500.html", status=500)


def page_not_found_view(
    request,
    exception=None,
    template_name="buddy_crocker/404.html",
):  # pylint: disable=unused-argument
    """Display template for 404 page."""
    return render(request, template_name, status=404)


def server_error_view(
    request,
    exception=None,
    template_name="buddy_crocker/500.html",
):  # pylint: disable=unused-argument
    """Display server error template."""
    return render(request, template_name, status=500)


@require_http_methods(["GET"])
def search_usda_ingredients(request):
    """
    AJAX endpoint to search USDA database for ingredients.

    Returns:
        JsonResponse with results or standardized error format.
    """
    query = request.GET.get("q", "").strip()

    if not query or len(query) < 2:
        return JsonResponse({"results": []})

    try:
        results = usda_service.search_usda_foods(query, Allergen.objects.all())
        return JsonResponse({"results": results})

    except usda_api.USDAAPIKeyError:
        logger.critical("Invalid USDA API key in search")
        return JsonResponse(
            {
                "error": "configuration_error",
                "message": "Service configuration error. Please contact support.",
            },
            status=500,
        )

    except usda_api.USDAAPIRateLimitError:
        logger.warning(
            "USDA API rate limit hit during search for query: %s",
            query,
        )
        return JsonResponse(
            {
                "error": "rate_limit_exceeded",
                "message": "Too many requests. Please try again in a moment.",
            },
            status=429,
        )

    except usda_api.USDAAPIError as exc:
        logger.error("USDA API error during search: %s", str(exc))
        return JsonResponse(
            {
                "error": "search_failed",
                "message": (
                    "Unable to search ingredients at this time. "
                    "Please try again later."
                ),
            },
            status=503,
        )

    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Unexpected error during USDA search")
        return JsonResponse(
            {
                "error": "internal_error",
                "message": "An unexpected error occurred. Please try again.",
            },
            status=500,
        )


@require_http_methods(["POST"])
@login_required
def scan_pantry(request):
    """Scan pantry image and extract ingredients using GPT-4 Vision."""
    logger.info("Pantry scan request from user: %s", request.user.username)

    try:
        result = process_pantry_scan(request)
        return JsonResponse(result, status=result.get("status_code", 200))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Unexpected error during scan: %s", str(exc))
        return JsonResponse(
            {
                "success": False,
                "error": "An unexpected error occurred. Please try again.",
            },
            status=500,
        )


@require_http_methods(["POST"])
@login_required
def add_scanned_ingredients(request):
    """Add confirmed scanned ingredients to user's pantry."""
    logger.info(
        "Add scanned ingredients request from user: %s",
        request.user.username,
    )

    try:
        data = json.loads(request.body)
        ingredients_data = data.get("ingredients", [])

        if not ingredients_data:
            return JsonResponse(
                {
                    "success": False,
                    "error": "No ingredients provided",
                },
                status=400,
            )

        result = add_ingredients_to_pantry(request.user, ingredients_data)
        return JsonResponse(result)

    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return JsonResponse(
            {
                "success": False,
                "error": "Invalid JSON data",
            },
            status=400,
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Error adding scanned ingredients: %s", str(exc))
        return JsonResponse(
            {
                "success": False,
                "error": "Failed to add ingredients",
            },
            status=500,
        )


@login_required
def quick_add_ingredients(request, pk):
    """View to add ingredients from the recipe detail page."""
    recipe = get_object_or_404(Recipe, pk=pk)

    if request.user.is_authenticated:
        try:
            ingredient_id = request.POST.get("ingredient_id")
            ingredient = Ingredient.objects.get(pk=ingredient_id)

            _recipe_ing, created = RecipeIngredient.objects.get_or_create(
                recipe=recipe,
                ingredient=ingredient,
                defaults={"amount": 100.0, "unit": "g"},
            )

            if created:
                messages.success(
                    request,
                    f"Added {ingredient.name} to {recipe.title}!",
                )
            else:
                messages.info(
                    request,
                    f"{ingredient.name} already in {recipe.title}",
                )

        except Ingredient.DoesNotExist:
            messages.error(request, "Ingredient not found")

    return redirect("recipe-detail", pk=recipe.pk)


@login_required
def edit_ingredient(request, pk):
    """
    Edit an existing ingredient.
    """
    ingredient = get_object_or_404(Ingredient, pk=pk)

    if request.method == "POST":
        form = IngredientForm(request.POST, instance=ingredient)
        if form.is_valid():
            ingredient = form.save()
            messages.success(
                request,
                f"Successfully updated {ingredient.name}!",
            )
            return redirect("ingredient-detail", pk=ingredient.pk)
    else:
        form = IngredientForm(instance=ingredient)

    context = {
        "form": form,
        "ingredient": ingredient,
        "edit_mode": True,
    }
    return render(request, "buddy_crocker/add-ingredient.html", context)


@login_required
def delete_ingredient(request, pk):
    """View to delete ingredients from the pantry."""
    ingredient = get_object_or_404(Ingredient, pk=pk)

    if request.method == "POST":
        ingredient_name = ingredient.name
        ingredient.delete()
        messages.success(
            request,
            f"Successfully deleted {ingredient_name}!",
        )
        return redirect("pantry")

    context = {
        "ingredient": ingredient,
    }
    return render(request, "buddy_crocker/delete_ingredient_confirm.html", context)


@login_required
@transaction.atomic
def edit_recipe(request, pk):
    """Edit an existing recipe."""
    recipe = get_object_or_404(Recipe, pk=pk, author=request.user)

    if request.method == "POST":
        form = RecipeForm(request.POST, request.FILES, instance=recipe)
        formset = RecipeIngredientFormSet(request.POST, instance=recipe)

        if form.is_valid() and formset.is_valid():
            form.save()

            instances = formset.save(commit=False)
            for instance in instances:
                instance.auto_calculate_gram_weight()
                instance.save()

            for obj in formset.deleted_objects:
                obj.delete()

            messages.success(
                request,
                f'Recipe "{recipe.title}" updated!',
            )
            return redirect("recipe-detail", pk=recipe.pk)
    else:
        form = RecipeForm(instance=recipe)
        formset = RecipeIngredientFormSet(instance=recipe)

    try:
        pantry_obj = Pantry.objects.get(user=request.user)
        available_ingredients = pantry_obj.ingredients.all()
    except Pantry.DoesNotExist:
        available_ingredients = Ingredient.objects.none()

    context = {
        "form": form,
        "formset": formset,
        "recipe": recipe,
        "available_ingredients": available_ingredients,
        "edit_mode": True,
    }
    return render(request, "buddy_crocker/add_recipe.html", context)


@login_required
def delete_recipe(request, pk):
    """View to delete a recipe from the details page."""
    recipe = get_object_or_404(Recipe, pk=pk)

    if request.method == "POST":
        recipe_title = recipe.title
        recipe.delete()
        messages.success(
            request,
            f"Successfully deleted {recipe_title}!",
        )
        return redirect("recipe-search")

    context = {
        "recipe": recipe,
    }
    return render(request, "buddy_crocker/delete_recipe_confirm.html", context)


@login_required
@require_http_methods(["POST"])
def add_custom_portion(request, pk):
    """View to create a custom portion size of an ingredient."""
    ingredient = get_object_or_404(Ingredient, pk=pk)

    try:
        data = json.loads(request.body)

        portion_data = ingredient.portion_data or []
        portion_data.append(data)
        ingredient.portion_data = portion_data
        ingredient.save()

        return JsonResponse({"success": True})
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return JsonResponse(
            {"success": False, "error": str(exc)},
            status=400,
        )


@login_required
@require_http_methods(["GET", "POST"])
def ai_recipe_generator(request):
    """
    Generate recipes from selected pantry ingredients using OpenAI API.
    Allows saving recipes and adding ingredients to shopping list.
    """
    pantry_obj, _ = Pantry.objects.get_or_create(user=request.user)
    pantry_ingredients = pantry_obj.ingredients.all()

    # Get selected ingredients or all by default
    selected_ingredient_ids = request.session.get("selected_pantry_ingredients", [])
    if not selected_ingredient_ids:
        selected_ingredient_ids = [ing.id for ing in pantry_ingredients]

    selected_ingredients = pantry_ingredients.filter(id__in=selected_ingredient_ids)
    ingredient_names = [ing.name for ing in selected_ingredients if ing.name]

    error_msg = None
    recipes = request.session.get("ai_recipes", [])
    zipped_recipes_forms = []

    # 1. GENERATE RECIPES
    if request.method == "POST" and "generate_recipes" in request.POST:
        logger.info("Generate recipes button clicked by user %s", request.user.username)

        # Get selected ingredients from form
        selected_ids = request.POST.getlist("selected_ingredients")
        if selected_ids:
            selected_ingredient_ids = [int(id_str) for id_str in selected_ids]
            request.session["selected_pantry_ingredients"] = selected_ingredient_ids
            selected_ingredients = pantry_ingredients.filter(id__in=selected_ingredient_ids)
            ingredient_names = [ing.name for ing in selected_ingredients if ing.name]

        if not ingredient_names:
            error_msg = "Please select at least one ingredient."
            recipes = []
        else:
            try:
                recipes = generate_ai_recipes(ingredient_names)
                logger.info("Generated %d recipes for user %s", len(recipes), request.user.username)
            except RuntimeError as exc:
                error_msg = str(exc)
                logger.error("Recipe generation failed: %s", exc)
                recipes = []

        # Store in session
        request.session["ai_recipes"] = recipes
        request.session.modified = True

    # 2. SAVE RECIPE
    elif request.method == "POST":
        # Get recipes from session FIRST
        recipes = request.session.get("ai_recipes", [])
        logger.info("POST request - recipes in session: %d", len(recipes))
        logger.info("POST keys: %s", list(request.POST.keys()))

        # Check for save_recipe button
        recipe_index = None
        for key in request.POST:
            if key.startswith("save_recipe_"):
                try:
                    recipe_index = int(key.split("_")[-1]) - 1  # 1-based to 0-based
                    logger.info("Save recipe index: %d", recipe_index)
                    break
                except (ValueError, IndexError):
                    pass

        if recipe_index is not None and 0 <= recipe_index < len(recipes):
            recipe_data = recipes[recipe_index]
            logger.info("Saving recipe: %s", recipe_data.get("title"))
            try:
                saved_recipe = _save_recipe_for_user(request.user, recipe_data)
                messages.success(
                    request,
                    f'Recipe "{saved_recipe.title}" has been saved to'
                    'your profile!'
                )
                logger.info(
                    "User %s saved recipe: %s (ID: %d)",
                    request.user.username,
                    saved_recipe.title,
                    saved_recipe.id
                )
            except IntegrityError as exc:
                logger.error("Database error saving recipe: %s", exc)
                messages.error(request, "A recipe with this title already exists in your profile.")
            except Exception as exc:
                logger.error("Failed to save recipe: %s", exc)
                messages.error(request, f"Failed to save recipe: {exc}")

        # Check for add_to_shopping button
        elif any(k.startswith("add_to_shopping_") for k in request.POST):
            recipe_index = None
            for key in request.POST:
                if key.startswith("add_to_shopping_"):
                    try:
                        recipe_index = int(key.split("_")[-1]) - 1
                        break
                    except (ValueError, IndexError):
                        pass

            if recipe_index is not None:
                # Get checked ingredients for this recipe
                shopping_items = []
                for key, value in request.POST.items():
                    if key.startswith(f"shopping_{recipe_index + 1}_"):
                        shopping_items.append(value)

                if shopping_items:
                    try:
                        _add_to_shopping_list(request.user, shopping_items)
                        messages.success(
                            request,
                            f"Added {len(shopping_items)} ingredient(s) to shopping list!"
                        )
                        logger.info(
                            "User %s added %d items to shopping list",
                            request.user.username,
                            len(shopping_items)
                        )
                    except Exception as exc:
                        logger.error("Failed to add to shopping list: %s", exc)
                        messages.error(request, f"Failed to add to shopping list: {exc}")
                else:
                    messages.warning(request, "No ingredients selected.")

    # Build forms for display (get fresh recipes from session)
    recipes = request.session.get("ai_recipes", [])
    for idx, recipe in enumerate(recipes[:4]):
        form = SaveAIRecipeForm(prefix=f"recipe_{idx}")
        zipped_recipes_forms.append((recipe, form))

    logger.info("Rendering %d recipes for user %s", len(zipped_recipes_forms), request.user.username)

    context = {
        "pantry_ingredients": pantry_ingredients,
        "selected_ingredient_ids": selected_ingredient_ids,
        "ingredient_names": ingredient_names,
        "zipped_recipes_forms": zipped_recipes_forms,
        "error_msg": error_msg,
    }
    return render(request, "buddy_crocker/ai_recipe_generator.html", context)


def _get_clicked_recipe_index(post_data, button_prefix):
    """
    Extract recipe index from clicked button name.

    Args:
        post_data: POST data dict
        button_prefix: Button name prefix (e.g., 'save_recipe_')

    Returns:
        0-based recipe index or None if not found
    """
    for key in post_data:
        if key.startswith(button_prefix):
            try:
                return int(key.split("_")[-1]) - 1  # Convert 1-based to 0-based
            except (ValueError, IndexError):
                continue
    return None


def _save_recipe_for_user(user, recipe_data):
    """
    Create Recipe and RecipeIngredient objects for user.

    Args:
        user: User instance
        recipe_data: Dict with title, ingredients, instructions, uses_only_pantry

    Returns:
        Created Recipe instance

    Raises:
        IntegrityError: If recipe with same title exists
        ValueError: If recipe data is invalid
    """
    title = recipe_data.get("title", "").strip()
    instructions = recipe_data.get("instructions", "").strip()
    ingredients_list = recipe_data.get("ingredients", [])

    if not title:
        raise ValueError("Recipe title is required")
    if not instructions:
        raise ValueError("Recipe instructions are required")
    if not ingredients_list:
        raise ValueError("Recipe must have at least one ingredient")

    with transaction.atomic():
        # Create the recipe - USE 'author' to match your model
        recipe = Recipe.objects.create(
            author=user,
            title=title,
            instructions=instructions,
            servings=4,
            prep_time=0,
            cook_time=0,
            difficulty="medium",
        )

        # Add each ingredient
        for idx, ing_str in enumerate(ingredients_list):
            # Parse ingredient string
            amount, unit, name = _parse_ingredient_string(ing_str)

            # Get or create ingredient (case-insensitive lookup)
            ingredient_obj = Ingredient.objects.filter(name__iexact=name).first()
            if not ingredient_obj:
                ingredient_obj = Ingredient.objects.create(
                    name=name,
                    brand="Generic",
                    calories=0
                )

            # Create recipe-ingredient relationship
            RecipeIngredient.objects.create(
                recipe=recipe,
                ingredient=ingredient_obj,
                amount=amount,
                unit=unit,
                notes="",
                order=idx,
            )

        logger.info("Created recipe '%s' with %d ingredients for user %s",
                    title, len(ingredients_list), user.username)

    return recipe


def _parse_ingredient_string(ing_str):
    """
    Parse ingredient string into amount, unit, and name.

    Examples:
        "2 cups flour" -> (2.0, "cups", "flour")
        "1 lb chicken breast" -> (1.0, "lb", "chicken breast")
        "salt to taste" -> (1.0, "unit", "salt to taste")
        "1/2 cup milk" -> (0.5, "cup", "milk")

    Args:
        ing_str: Ingredient string from AI

    Returns:
        Tuple of (amount, unit, name)
    """
    parts = ing_str.strip().split(None, 2)

    # Try to parse "amount unit name" format
    if len(parts) >= 3:
        try:
            # Handle fractions
            amount_str = parts[0].replace("½", "0.5").replace("¼", "0.25").replace("¾", "0.75")
            # Handle "1/2" style fractions
            if "/" in amount_str:
                num, denom = amount_str.split("/")
                amount = float(num) / float(denom)
            else:
                amount = float(amount_str)
            unit = parts[1]
            name = parts[2]
            return amount, unit, name
        except (ValueError, ZeroDivisionError):
            pass

    # Try to parse "amount name" format (no unit)
    if len(parts) >= 2:
        try:
            amount_str = parts[0].replace("½", "0.5").replace("¼", "0.25").replace("¾", "0.75")
            if "/" in amount_str:
                num, denom = amount_str.split("/")
                amount = float(num) / float(denom)
            else:
                amount = float(amount_str)
            name = " ".join(parts[1:])
            return amount, "unit", name
        except (ValueError, ZeroDivisionError):
            pass

    # Default: treat whole string as name with amount of 1
    return 1.0, "unit", ing_str.strip()


def _add_recipe_to_shopping_list(request, recipe_data):
    """
    Add selected recipe ingredients to shopping list.

    Args:
        request: HTTP request object
        recipe_data: Dictionary containing recipe information from AI

    Returns:
        int: Number of items successfully added
    """
    added_count = 0

    for ingredient_text in recipe_data.get('ingredients', []):
        try:
            # Parse ingredient text (you may need more sophisticated parsing)
            ingredient_name = ingredient_text.strip()

            ShoppingListItem.objects.create(
                user=request.user,
                ingredient_name=ingredient_name,
                quantity='',  # Could parse this from ingredient_text
                notes=f'From recipe: {recipe_data.get("title", "AI Generated")}'
            )
            added_count += 1
        except IntegrityError:
            # Item already exists, skip
            continue
        except ValidationError:
            # Invalid data, skip
            continue

    return added_count

def _parse_ingredient_string(ing_str):
    """
    Parse ingredient string into amount, unit, and name.

    Examples:
        "2 cups flour" -> (2.0, "cups", "flour")
        "1 lb chicken breast" -> (1.0, "lb", "chicken breast")
        "salt to taste" -> (1.0, "unit", "salt to taste")
        "1/2 cup milk" -> (0.5, "cup", "milk")

    Args:
        ing_str: Ingredient string from AI

    Returns:
        Tuple of (amount, unit, name)
    """
    parts = ing_str.strip().split(None, 2)

    # Try to parse "amount unit name" format
    if len(parts) >= 3:
        try:
            # Handle fractions
            amount_str = parts[0].replace("½", "0.5").replace("¼", "0.25").replace("¾", "0.75")
            # Handle "1/2" style fractions
            if "/" in amount_str:
                num, denom = amount_str.split("/")
                amount = float(num) / float(denom)
            else:
                amount = float(amount_str)
            unit = parts[1]
            name = parts[2]
            return amount, unit, name
        except (ValueError, ZeroDivisionError):
            pass

    # Try to parse "amount name" format (no unit)
    if len(parts) >= 2:
        try:
            amount_str = parts[0].replace("½", "0.5").replace("¼", "0.25").replace("¾", "0.75")
            if "/" in amount_str:
                num, denom = amount_str.split("/")
                amount = float(num) / float(denom)
            else:
                amount = float(amount_str)
            name = " ".join(parts[1:])
            return amount, "unit", name
        except (ValueError, ZeroDivisionError):
            pass

    # Default: treat whole string as name with amount of 1
    return 1.0, "unit", ing_str.strip()

def _add_to_shopping_list(user, shopping_items):
    """
    Add ingredients to user's shopping list.

    Args:
        user: User instance
        shopping_items: List of ingredient strings to add
    
    Returns:
        int: Number of items successfully added
    """
    from django.core.exceptions import ValidationError
    
    added_count = 0
    skipped_count = 0
    
    for ingredient_text in shopping_items:
        try:
            # Parse ingredient text (e.g., "2 cups flour" -> amount, unit, name)
            amount, unit, name = _parse_ingredient_string(ingredient_text)
            
            # Format quantity string
            if amount and unit:
                quantity = f"{amount} {unit}".strip()
                # Clean up "1.0 unit" to empty string
                if quantity == "1.0 unit":
                    quantity = ""
            else:
                quantity = ""
            
            # Try to find matching ingredient in database (case-insensitive)
            ingredient_obj = Ingredient.objects.filter(
                name__iexact=name
            ).first()
            
            # Create shopping list item
            ShoppingListItem.objects.create(
                user=user,
                ingredient=ingredient_obj,  # May be None if not in database
                ingredient_name=name,
                quantity=quantity,
                notes='From AI recipe'
            )
            added_count += 1
            logger.info("Added '%s' to shopping list for user %s", name, user.username)
            
        except IntegrityError:
            # Item already exists in shopping list, skip
            logger.debug("Shopping item '%s' already exists for user %s", name, user.username)
            skipped_count += 1
            continue
            
        except ValidationError as exc:
            # Invalid data, skip
            logger.warning("Validation error adding shopping item: %s", exc)
            continue
            
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # Unexpected error, log and continue
            logger.error("Error adding shopping item '%s': %s", ingredient_text, exc)
            continue
    
    logger.info(
        "Added %d items to shopping list for user %s (%d skipped/duplicates)", 
        added_count, 
        user.username,
        skipped_count
    )
    return added_count


@login_required
@require_http_methods(["GET", "POST"])
def shopping_list_view(request):
    """
    Display and manage user shopping list with CSRF protection.

    GET: Display shopping list with add form
    POST: Handle add, toggle, delete, clear operations
    """
    if request.method == 'POST':
        return _handle_shopping_list_post(request)

    # GET request - display shopping list
    items = ShoppingListItem.objects.filter(user=request.user)
    form = ShoppingListItemForm()

    context = {
        'items': items,
        'form': form,
        'purchased_count': items.filter(is_purchased=True).count(),
        'pending_count': items.filter(is_purchased=False).count(),
        'total_count': items.count(),
    }

    return render(request, 'buddy_crocker/shopping_list.html', context)


def _handle_shopping_list_post(request):
    """
    Handle POST requests for shopping list operations.

    Security: All operations verify user ownership before modification.
    """
    # Add new item
    if 'add_item' in request.POST:
        return _add_shopping_item(request)

    # Toggle purchased status
    if 'toggle_purchased' in request.POST:
        return _toggle_purchased(request)

    # Delete item
    if 'delete_item' in request.POST:
        return _delete_item(request)

    # Clear purchased items
    if 'clear_purchased' in request.POST:
        return _clear_purchased_items(request)

    # Add to pantry
    if 'add_to_pantry' in request.POST:
        return _add_to_pantry(request)

    messages.error(request, 'Invalid action.')
    return redirect('shopping-list')


def _add_shopping_item(request):
    """Add a new item to the shopping list with validation."""
    form = ShoppingListItemForm(request.POST)

    if form.is_valid():
        try:
            item = form.save(commit=False)
            item.user = request.user
            item.save()
            messages.success(
                request,
                f'Added "{item.ingredient_name}" to your shopping list.'
            )
        except (IntegrityError, ValidationError):  # Catch both
            messages.warning(
                request,
                'This item is already in your shopping list.'
            )
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{field}: {error}')

    return redirect('shopping-list')


def _toggle_purchased(request):
    """Toggle the purchased status of an item."""
    item_id = request.POST.get('toggle_purchased')

    if not item_id or not item_id.isdigit():
        messages.error(request, 'Invalid item ID.')
        return redirect('shopping-list')

    item = get_object_or_404(
        ShoppingListItem,
        id=int(item_id),
        user=request.user
    )
    item.toggle_purchased()

    status = 'purchased' if item.is_purchased else 'pending'
    messages.success(
        request,
        f'Marked "{item.ingredient_name}" as {status}.'
    )

    return redirect('shopping-list')


def _delete_item(request):
    """Delete a shopping list item after verifying ownership."""
    item_id = request.POST.get('delete_item')

    if not item_id or not item_id.isdigit():
        messages.error(request, 'Invalid item ID.')
        return redirect('shopping-list')

    item = get_object_or_404(
        ShoppingListItem,
        id=int(item_id),
        user=request.user
    )
    item_name = item.ingredient_name
    item.delete()
    messages.success(
        request,
        f'Removed "{item_name}" from your shopping list.'
    )

    return redirect('shopping-list')


def _clear_purchased_items(request):
    """Clear all purchased items from the shopping list."""
    deleted_count, _ = ShoppingListItem.objects.filter(
        user=request.user,
        is_purchased=True
    ).delete()

    if deleted_count > 0:
        messages.success(
            request,
            f'Cleared {deleted_count} purchased item(s) from your list.'
        )
    else:
        messages.info(request, 'No purchased items to clear.')

    return redirect('shopping-list')


def _add_to_pantry(request):
    """Add purchased shopping item to pantry if linked to ingredient."""
    item_id = request.POST.get('add_to_pantry')

    if not item_id or not item_id.isdigit():
        messages.error(request, 'Invalid item ID.')
        return redirect('shopping-list')

    item = get_object_or_404(
        ShoppingListItem,
        id=int(item_id),
        user=request.user
    )

    if item.add_to_pantry():
        messages.success(
            request,
            f'Added "{item.ingredient_name}" to your pantry.'
        )
    else:
        messages.warning(
            request,
            'Cannot add to pantry: no linked ingredient.'
        )

    return redirect('shopping-list')
    