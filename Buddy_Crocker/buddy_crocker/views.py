"""Views for Buddy Crocker meal planning and recipe management app."""
import json
import logging

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST, require_http_methods

from services.allergen_service import (
    get_user_allergens,
    get_allergen_context,
    categorize_pantry_ingredients
)
from services.recipe_service import filter_recipes_by_allergens
from services.usda_service import search_usda_foods
from services.scan_service import process_pantry_scan, add_ingredients_to_pantry
from .forms import (
    CustomUserCreationForm,
    IngredientForm,
    ProfileForm,
    RecipeForm,
    UserForm
)
from .models import Allergen, Ingredient, Pantry, Profile, Recipe

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
        return reverse('profile-detail', kwargs={'pk': self.request.user.pk})


def register(request):
    """Handle user registration with automatic login after signup."""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect('profile-detail', pk=user.pk)
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


def index(request):
    """Render the home page with featured recipes."""
    recent_recipes = Recipe.objects.all()[:6]
    context = {'recent_recipes': recent_recipes}
    return render(request, 'buddy_crocker/index.html', context)


def recipe_search(request):
    """Display recipe search/browse page with optional filtering."""
    recipes = Recipe.objects.all().select_related('author').prefetch_related(
        'ingredients'
    )

    # Search by title
    search_query = request.GET.get('q', '')
    if search_query:
        recipes = recipes.filter(title__icontains=search_query)

    # Get user allergen info
    user_allergens, user_profile_allergen_ids = get_user_allergens(request.user)

    # Filter by allergens
    exclude_allergens = request.GET.getlist('exclude_allergens')
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
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'recipes': page_obj,
        'all_allergens': Allergen.objects.all(),
        'selected_allergen_ids': selected_allergen_ids,
        'user_profile_allergen_ids': user_profile_allergen_ids,
        'search_query': search_query,
        'total_count': paginator.count,
    }
    return render(request, 'buddy_crocker/recipe-search.html', context)


def recipe_detail(request, pk):
    """Display detailed information about a specific recipe."""
    recipe = get_object_or_404(Recipe, pk=pk)
    ingredients = recipe.ingredients.all()
    all_recipe_allergens = recipe.get_allergens()

    user_allergens, _ = get_user_allergens(request.user)
    allergen_ctx = get_allergen_context(all_recipe_allergens, user_allergens)

    context = {
        'recipe': recipe,
        'ingredients': ingredients,
        'all_recipe_allergens': all_recipe_allergens,
        'user_allergens': user_allergens or [],
        **allergen_ctx,
    }
    return render(request, 'buddy_crocker/recipe_detail.html', context)


def ingredient_detail(request, pk):
    """Display detailed information about a specific ingredient."""
    ingredient = get_object_or_404(Ingredient, pk=pk)
    all_allergens = ingredient.allergens.all()
    related_recipes = ingredient.recipes.all()

    user_allergens, _ = get_user_allergens(request.user)
    allergen_ctx = get_allergen_context(all_allergens, user_allergens)

    context = {
        'ingredient': ingredient,
        'all_allergens': all_allergens,
        'user_allergens': user_allergens or [],
        'related_recipes': related_recipes,
        **allergen_ctx,
    }
    return render(request, 'buddy_crocker/ingredient_detail.html', context)


def allergen_detail(request, pk):
    """Display detailed information about a specific allergen."""
    allergen = get_object_or_404(Allergen, pk=pk)
    affected_ingredients = allergen.ingredients.all()
    affected_recipes = Recipe.objects.filter(
        ingredients__allergens=allergen
    ).distinct()

    can_add_to_profile = False
    already_in_profile = False
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            already_in_profile = allergen in profile.allergens.all()
            can_add_to_profile = not already_in_profile
        except Profile.DoesNotExist:
            pass

    context = {
        'allergen': allergen,
        'affected_ingredients': affected_ingredients,
        'affected_recipes': affected_recipes,
        'can_add_to_profile': can_add_to_profile,
        'already_in_profile': already_in_profile,
    }
    return render(request, 'buddy_crocker/allergen_detail.html', context)


@login_required
def pantry(request):
    """Display and manage the user's pantry with allergen warnings."""
    pantry_obj, _ = Pantry.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        ingredient_id = request.POST.get('ingredient_id')

        if ingredient_id:
            ingredient = get_object_or_404(Ingredient, pk=ingredient_id)
            if action == 'add':
                pantry_obj.ingredients.add(ingredient)
            elif action == 'remove':
                pantry_obj.ingredients.remove(ingredient)
        return redirect('pantry')

    pantry_ingredients = pantry_obj.ingredients.all().prefetch_related(
        'allergens'
    )
    user_allergens, _ = get_user_allergens(request.user)
    show_allergen_warnings = bool(user_allergens)

    # Categorize ingredients
    safe_ingredients, unsafe_ingredients = categorize_pantry_ingredients(
        pantry_ingredients, user_allergens
    )

    context = {
        'pantry': pantry_obj,
        'safe_ingredients': safe_ingredients,
        'unsafe_ingredients': unsafe_ingredients,
        'user_allergens': user_allergens,
        'show_allergen_warnings': show_allergen_warnings,
        'total_ingredients': pantry_ingredients.count(),
        'unsafe_count': len(unsafe_ingredients),
        'safe_count': len(safe_ingredients),
        'all_ingredients': Ingredient.objects.all(),
        'pantry_ingredient_ids': set(
            pantry_obj.ingredients.values_list('id', flat=True)
        ),
    }
    return render(request, 'buddy_crocker/pantry.html', context)


@login_required
def add_ingredient(request):
    """Create a new ingredient."""
    if request.method == 'POST':
        form = IngredientForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            calories = form.cleaned_data['calories']
            allergens = form.cleaned_data['allergens']
            brand = form.cleaned_data['brand']

            ingredient, created = Ingredient.objects.get_or_create(
                name=name,
                brand=brand,
                defaults={'calories': calories}
            )

            if not created and ingredient.calories != calories:
                ingredient.calories = calories
                ingredient.save()

            ingredient.allergens.set(allergens)

            if request.user.is_authenticated:
                user_pantry, _ = Pantry.objects.get_or_create(
                    user=request.user
                )
                if ingredient not in user_pantry.ingredients.all():
                    user_pantry.ingredients.add(ingredient)

            return redirect('ingredient-detail', pk=ingredient.pk)
        messages.error(request, "Please fix the errors below before submitting.")
    else:
        form = IngredientForm()

    return render(request, 'buddy_crocker/add-ingredient.html', {'form': form})


@login_required
def add_recipe(request):
    """Display form to add a new recipe."""
    if request.method == "POST":
        form = RecipeForm(request.POST)
        if form.is_valid():
            title = (form.cleaned_data.get("title") or "").strip()
            if Recipe.objects.filter(
                author=request.user,
                title__iexact=title
            ).exists():
                form.add_error(
                    "title",
                    "You already have a recipe with this title. "
                    "Choose a different title."
                )
                messages.error(request, "Please correct the errors below.")
                return render(
                    request,
                    "buddy_crocker/add_recipe.html",
                    {"form": form}
                )

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
                    "You already have a recipe with this title. "
                    "Choose a different title."
                )
                messages.error(
                    request,
                    "There was a problem saving your recipe. Please try again."
                )
                return render(
                    request,
                    "buddy_crocker/add_recipe.html",
                    {"form": form}
                )
        messages.error(request, "Please fix the errors below")
    else:
        form = RecipeForm()

    return render(request, 'buddy_crocker/add_recipe.html', {'form': form})


@login_required
def profile_detail(request, pk):
    """Display and edit user profile."""
    if request.user.pk != pk:
        return redirect('profile-detail', pk=request.user.pk)

    user = get_object_or_404(User, pk=pk)
    profile, _ = Profile.objects.get_or_create(user=user)
    user_pantry, _ = Pantry.objects.get_or_create(user=user)
    pantry_ingredient_ids = set(
        user_pantry.ingredients.values_list('id', flat=True)
    )

    safe_recipes = profile.get_safe_recipes()
    recipes_you_can_make = [
        recipe for recipe in safe_recipes
        if set(recipe.ingredients.values_list('id', flat=True)).issubset(
            pantry_ingredient_ids
        )
    ]

    edit_mode = request.GET.get('edit') == '1'

    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=user)
        profile_form = ProfileForm(request.POST, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            return redirect('profile-detail', pk=pk)
    else:
        user_form = UserForm(instance=user)
        profile_form = ProfileForm(instance=profile)

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'user': user,
        'profile': profile,
        'pantry': user_pantry,
        'recipes_you_can_make': recipes_you_can_make,
        'edit_mode': edit_mode,
        'safe_recipe_count': safe_recipes.count(),
        'total_recipe_count': Recipe.objects.count(),
    }
    return render(request, 'buddy_crocker/profile_detail.html', context)


def preview_404(request):
    """Display template for 404 page."""
    return render(request, "buddy_crocker/404.html", status=404)


def preview_500(request):
    """Display server error template."""
    return render(request, "buddy_crocker/500.html", status=500)


def page_not_found_view(
    request, exception=None, template_name="buddy_crocker/404.html"
): # pylint: disable=unused-argument
    """Display template for 404 page."""
    return render(request, template_name, status=404)


def server_error_view(
    request, exception=None, template_name="buddy_crocker/500.html"
): # pylint: disable=unused-argument
    """Display server error template."""
    return render(request, template_name, status=500)


@require_http_methods(["GET"])
def search_usda_ingredients(request):
    """AJAX endpoint to search USDA database for ingredients."""
    query = request.GET.get('q', '').strip()

    if not query or len(query) < 2:
        return JsonResponse({'results': []})

    try:
        results = search_usda_foods(query, Allergen.objects.all())
        return JsonResponse({'results': results})
    except Exception as e: # pylint: disable=broad-exception-caught
        logger.error("USDA search error: %s", str(e))
        return JsonResponse({
            'error': f"Failed to search USDA database: {str(e)}"
        }, status=500)


@require_http_methods(["POST"])
@login_required
def scan_pantry(request):
    """Scan pantry image and extract ingredients using GPT-4 Vision."""
    logger.info("Pantry scan request from user: %s", request.user.username)

    try:
        result = process_pantry_scan(request)
        return JsonResponse(result, status=result.get('status_code', 200))
    except Exception as e: # pylint: disable=broad-exception-caught
        logger.error("Unexpected error during scan: %s", str(e))
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred. Please try again.'
        }, status=500)


@require_http_methods(["POST"])
@login_required
def add_scanned_ingredients(request):
    """Add confirmed scanned ingredients to user's pantry."""
    logger.info(
        "Add scanned ingredients request from user: %s",
        request.user.username
    )

    try:
        data = json.loads(request.body)
        ingredients_data = data.get('ingredients', [])

        if not ingredients_data:
            return JsonResponse({
                'success': False,
                'error': 'No ingredients provided'
            }, status=400)

        result = add_ingredients_to_pantry(request.user, ingredients_data)
        return JsonResponse(result)

    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e: # pylint: disable=broad-exception-caught
        logger.error("Error adding scanned ingredients: %s", str(e))
        return JsonResponse({
            'success': False,
            'error': 'Failed to add ingredients'
        }, status=500)
