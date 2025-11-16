"""
Views for Buddy Crocker meal planning and recipe management app."""
# Standard library
import os
import sys
import json
import base64
import logging
from typing import List, Dict
from openai import OpenAI

# Django
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods
from requests.exceptions import RequestException, Timeout

# Project imports
from services import usda_api
from services.ingredient_validator import USDAIngredientValidator
from .forms import CustomUserCreationForm, IngredientForm, ProfileForm, RecipeForm, UserForm
from .models import Allergen, Ingredient, Pantry, Profile, Recipe, ScanRateLimit

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
        """Determine the redirect URL after successful login.
        
        Redirects to the user's profile detail page using their primary key.
        This ensures users are redirected to their own profile page after login.
        """
        return reverse('profile-detail', kwargs={'pk': self.request.user.pk})

def register(request):
    """Handle user registration with automatic login after signup.
    
    Displays a user registration form (GET) and processes form submission (POST).
    On successful registration, creates a new user account, automatically logs
    the user in, and redirects to their profile detail page.
    """
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)  # Automatically log in user after registration
            return redirect('profile-detail', pk=user.pk)  # Redirect to profile detail page
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

def index(request):
    """
    Render the home page with featured recipes.
    
    Public view accessible to all users.
    """
    recent_recipes = Recipe.objects.all()[:6]

    context = {
        'recent_recipes': recent_recipes,
    }
    return render(request, 'buddy_crocker/index.html', context)

def _get_user_allergen_info(request):
    """
    Helper function to extract user allergen information.
    
    Returns:
        tuple: (user_allergens, user_profile_allergen_ids)
    """
    user_allergens = []
    user_profile_allergen_ids = []

    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            user_allergens = list(profile.allergens.all())
            user_profile_allergen_ids = [a.id for a in user_allergens]
        except Profile.DoesNotExist:
            pass

    return user_allergens, user_profile_allergen_ids

def _filter_recipes_by_allergens(recipes, exclude_allergen_ids):
    """
    Helper function to filter recipes by allergens.
    
    Args:
        recipes: QuerySet of recipes
        exclude_allergen_ids: List of allergen IDs to exclude
        
    Returns:
        Filtered QuerySet of recipes
    """
    # Get recipes that contain ingredients with excluded allergens
    recipes_with_allergens = Recipe.objects.filter(
        ingredients__allergens__id__in=exclude_allergen_ids
    ).distinct()

    # Exclude those recipes
    return recipes.exclude(id__in=recipes_with_allergens)

def recipe_search(request):
    """
    Display recipe search/browse page with optional filtering.
    
    Public view accessible to all users.
    Query parameters:
        - q: Search query for recipe title
        - exclude_allergens: List of allergen IDs to exclude
    """
    recipes = Recipe.objects.all().select_related('author').prefetch_related('ingredients')

    # Search by title
    search_query = request.GET.get('q', '')
    if search_query:
        recipes = recipes.filter(title__icontains=search_query)

    # Filter by allergens (exclude recipes with specified allergens)
    exclude_allergens = request.GET.getlist('exclude_allergens')
    if exclude_allergens:
        recipes = _filter_recipes_by_allergens(
            recipes,
            [int(aid) for aid in exclude_allergens if aid.isdigit()]
        )

    # Get all allergens for filter form
    all_allergens = Allergen.objects.all()

    # Get user's profile allergens
    user_allergens, user_profile_allergen_ids = _get_user_allergen_info(request)

    # Determine which allergens are currently selected in the filter
    # If user hasn't selected any, default to their profile allergens
    if exclude_allergens:
        selected_allergen_ids = [int(aid) for aid in exclude_allergens if aid.isdigit()]
    else:
        selected_allergen_ids = user_profile_allergen_ids

    # Add metadata to each recipe
    recipes_with_info = []
    for recipe in recipes:
        recipe.ingredient_count = recipe.ingredients.count()

        # Check if safe for user (only if authenticated and has allergen preferences)
        if request.user.is_authenticated and user_allergens:
            recipe_allergens = recipe.get_allergens()
            # Check if any of the recipe's allergens match user's allergens
            recipe.is_safe_for_user = not any(
                allergen in user_allergens
                for allergen in recipe_allergens
            )
        else:
            recipe.is_safe_for_user = None  # Unknown/not applicable

        recipes_with_info.append(recipe)

    # Pagination
    paginator = Paginator(recipes_with_info, 12)  # 12 recipes per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'recipes': page_obj,  # For backward compatibility
        'all_allergens': all_allergens,
        'selected_allergen_ids': selected_allergen_ids,  # Currently filtered allergens
        'user_profile_allergen_ids': user_profile_allergen_ids,  # User's profile allergens
        'search_query': search_query,
        'total_count': paginator.count,
    }
    return render(request, 'buddy_crocker/recipe-search.html', context)

def _get_allergen_context(all_allergens, user_allergens):
    """
    Helper function to determine allergen display context.
    
    Args:
        all_allergens: All allergens for the item
        user_allergens: User's allergen preferences
        
    Returns:
        dict: Context with allergen information
    """
    relevant_allergens = []
    has_allergen_conflict = False
    is_safe_for_user = False
    show_all_allergens = True

    if user_allergens:
        # User has allergen preferences - show only relevant ones
        show_all_allergens = False
        relevant_allergens = [a for a in all_allergens if a in user_allergens]
        has_allergen_conflict = len(relevant_allergens) > 0
        is_safe_for_user = len(relevant_allergens) == 0
    elif user_allergens is not None:
        # User is authenticated but has no allergen preferences
        show_all_allergens = False
        is_safe_for_user = True

    return {
        'relevant_allergens': relevant_allergens,
        'has_allergen_conflict': has_allergen_conflict,
        'is_safe_for_user': is_safe_for_user,
        'show_all_allergens': show_all_allergens,
    }

def recipe_detail(request, pk):
    """
    Display detailed information about a specific recipe.

    Shows personalized allergen warnings based on user's profile.
    - Authenticated users with allergen preferences: Only see their allergens
    - Authenticated users without preferences: No warnings shown
    - Unauthenticated users: See all allergens (safety first)

    Public view accessible to all users.
    """
    recipe = get_object_or_404(Recipe, pk=pk)
    ingredients = recipe.ingredients.all()
    all_recipe_allergens = recipe.get_allergens()

    # Get user allergen preferences
    user_allergens = None
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            user_allergens = list(profile.allergens.all())
        except Profile.DoesNotExist:
            pass

    # Get allergen context
    allergen_ctx = _get_allergen_context(all_recipe_allergens, user_allergens)

    context = {
        'recipe': recipe,
        'ingredients': ingredients,
        'all_recipe_allergens': all_recipe_allergens,
        'user_allergens': user_allergens or [],
        **allergen_ctx,
    }
    return render(request, 'buddy_crocker/recipe_detail.html', context)

def ingredient_detail(request, pk):
    """
    Display detailed information about a specific ingredient.

    Shows personalized allergen warnings based on user's profile.
    - Authenticated users: Only see warnings for their allergens
    - Unauthenticated users: See all allergens (safety first)

    Public view accessible to all users.

    Args:
        pk: Primary key of the ingredient
    """
    ingredient = get_object_or_404(Ingredient, pk=pk)
    all_allergens = ingredient.allergens.all()
    related_recipes = ingredient.recipes.all()

    # Get user allergen preferences
    user_allergens = None
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            user_allergens = list(profile.allergens.all())
        except Profile.DoesNotExist:
            pass

    # Get allergen context
    allergen_ctx = _get_allergen_context(all_allergens, user_allergens)

    context = {
        'ingredient': ingredient,
        'all_allergens': all_allergens,
        'user_allergens': user_allergens or [],
        'related_recipes': related_recipes,
        **allergen_ctx,
    }
    return render(request, 'buddy_crocker/ingredient_detail.html', context)

def allergen_detail(request, pk):
    """
    Display detailed information about a specific allergen.

    Public view accessible to all users.

    Args:
        pk: Primary key of the allergen
    """
    allergen = get_object_or_404(Allergen, pk=pk)

    # Get ingredients containing this allergen
    affected_ingredients = allergen.ingredients.all()

    # Get recipes containing this allergen (through ingredients)
    affected_recipes = Recipe.objects.filter(
        ingredients__allergens=allergen
    ).distinct()

    # Check if user can add this to their profile
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

def _categorize_pantry_ingredients(pantry_ingredients, user_allergens):
    """
    Helper function to categorize pantry ingredients as safe or unsafe.
    
    Args:
        pantry_ingredients: QuerySet of ingredients
        user_allergens: List of user's allergens
        
    Returns:
        tuple: (safe_ingredients, unsafe_ingredients)
    """
    safe_ingredients = []
    unsafe_ingredients = []

    for ingredient in pantry_ingredients:
        ingredient_allergens = list(ingredient.allergens.all())
        relevant_allergens = [a for a in ingredient_allergens if a in user_allergens]

        # Add custom attributes for template
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
    Display and manage the user's pantry with personalized allergen warnings.

    Shows allergen warnings only for ingredients containing user's allergens.
    Categorizes ingredients as safe/unsafe based on user profile.

    Login required view.
    """
    # Get or create pantry for user
    pantry_obj, _created = Pantry.objects.get_or_create(user=request.user)

    # Handle POST request to add/remove ingredients
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

    # Get all ingredients in pantry
    pantry_ingredients = pantry_obj.ingredients.all().prefetch_related('allergens')

    # Get user allergens
    user_allergens = []
    show_allergen_warnings = False

    try:
        profile = request.user.profile
        user_allergens = list(profile.allergens.all())
        show_allergen_warnings = bool(user_allergens)
    except Profile.DoesNotExist:
        pass

    # Categorize ingredients
    if user_allergens:
        safe_ingredients, unsafe_ingredients = _categorize_pantry_ingredients(
            pantry_ingredients, user_allergens
        )
    else:
        # User has no allergen preferences - all are safe
        safe_ingredients = []
        unsafe_ingredients = []
        for ingredient in pantry_ingredients:
            ingredient.relevant_allergens = []
            ingredient.has_conflict = False
            ingredient.is_safe = True
            safe_ingredients.append(ingredient)

    # Get all available ingredients for adding
    all_ingredients = Ingredient.objects.all()
    pantry_ingredient_ids = set(pantry_obj.ingredients.values_list('id', flat=True))

    context = {
        'pantry': pantry_obj,
        'safe_ingredients': safe_ingredients,
        'unsafe_ingredients': unsafe_ingredients,
        'user_allergens': user_allergens,
        'show_allergen_warnings': show_allergen_warnings,
        'total_ingredients': pantry_ingredients.count(),
        'unsafe_count': len(unsafe_ingredients),
        'safe_count': len(safe_ingredients),
        'all_ingredients': all_ingredients,
        'pantry_ingredient_ids': pantry_ingredient_ids,
    }
    return render(request, 'buddy_crocker/pantry.html', context)

@login_required
def add_ingredient(request):
    """
    Create a new ingredient.
    Login required view.
    """
    if request.method == 'POST':
        form = IngredientForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            calories = form.cleaned_data['calories']
            allergens = form.cleaned_data['allergens']
            brand = form.cleaned_data['brand']

            # Use get_or_create - reuses existing or creates new
            ingredient, created = Ingredient.objects.get_or_create(
                name=name,
                brand=brand,
                defaults={'calories': calories}
            )

            # Update calories if ingredient existed but has different value
            if not created and ingredient.calories != calories:
                ingredient.calories = calories
                ingredient.save()

            # Always update allergens
            ingredient.allergens.set(allergens)

            # Add to pantry (checking if already there)
            if request.user.is_authenticated:
                user_pantry, _created = Pantry.objects.get_or_create(user=request.user)

                if ingredient not in user_pantry.ingredients.all():
                    user_pantry.ingredients.add(ingredient)

            return redirect('ingredient-detail', pk=ingredient.pk)
        messages.error(request, "Please fix the errors below before submitting.")
    else:
        form = IngredientForm()

    return render(request, 'buddy_crocker/add-ingredient.html', {'form': form})

@login_required
def add_recipe(request):
    """Displays form to add a new recipe"""
    if request.method == "POST":
        form = RecipeForm(request.POST)
        if form.is_valid():
            title = (form.cleaned_data.get("title") or "").strip()
            # 1) Prevent duplicate title for this author (case-insensitive)
            if Recipe.objects.filter(author=request.user, title__iexact=title).exists():
                form.add_error("title", "You already have a recipe with this title. "
                                        "Choose a different title.")
                messages.error(request, "Please correct the errors below.")
                return render(request, "buddy_crocker/add_recipe.html", {"form": form})
            # 2) Save safely (guard against race-condition IntegrityError)
            recipe = form.save(commit=False)
            recipe.author = request.user
            recipe.title = title  # â† save the stripped title
            try:
                recipe.save()
                form.save_m2m()
                messages.success(request, "Recipe added successfully!")
                return redirect("recipe-detail", pk=recipe.pk)
            except IntegrityError:
                form.add_error(
                    "title", 
                    "You already have a recipe with this title. Choose a different title."
                    )
                messages.error(request, "There was a problem saving your recipe. Please try again.")
                return render(request, "buddy_crocker/add_recipe.html", {"form": form})
        # form errors (e.g., missing fields) will render below before sumbitting")
        messages.error(request,"Please fix the errors below")
    else:
        form = RecipeForm()

    return render(request, 'buddy_crocker/add_recipe.html', {'form': form})

@login_required
def profile_detail(request, pk):
    """Display and edit user profile"""
    if request.user.pk != pk:
        return redirect('profile-detail', pk=request.user.pk)

    user = get_object_or_404(User, pk=pk)
    profile, _created = Profile.objects.get_or_create(user=user)

    user_pantry, _ = Pantry.objects.get_or_create(user=user)
    pantry_ingredient_ids = set(user_pantry.ingredients.values_list('id', flat=True))

    safe_recipes = profile.get_safe_recipes()

    recipes_you_can_make = []
    for recipe in safe_recipes:
        recipe_ingredient_ids = set(recipe.ingredients.values_list('id', flat=True))
        if recipe_ingredient_ids.issubset(pantry_ingredient_ids):
            recipes_you_can_make.append(recipe)

    edit_mode = request.GET.get('edit') == '1'

    if request.method == 'POST':
        # Bind both forms to POST data for validation and saving
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
    """Displays template for 404 page"""
    return render(request, "buddy_crocker/404.html", status=404)

def preview_500(request):
    """Displays server error template"""
    return render(request, "buddy_crocker/500.html", status=500)

def page_not_found_view(
        request,
        exception=None,
        template_name="buddy_crocker/404.html"
    ): # pylint: disable=unused-argument
    """Displays template for 404 page"""
    return render(request, template_name, status=404)

def server_error_view(
        request,
        exception=None,
        template_name="buddy_crocker/500.html"
    ): # pylint: disable=unused-argument
    """Displays server error template"""
    return render(request, template_name, status=500)

@require_http_methods(["GET"])
def search_usda_ingredients(request):
    """
    AJAX endpoint to search USDA database for ingredients.
    Returns JSON with ingredient data including brand and allergen suggestions.

    Query Parameters:
        q: Search query string

    Returns:
        JSON with results array containing:
        - name: Ingredient name
        - brand: Brand name or 'Generic'
        - calories: Calorie count
        - fdc_id: USDA Food Data Central ID
        - data_type: USDA data type
        - suggested_allergens: Array of detected allergens
    """
    query = request.GET.get('q', '').strip()

    if not query or len(query) < 2:
        return JsonResponse({'results': []})

    # Import USDA API
    current_dir = os.path.dirname(os.path.abspath(__file__))
    services_dir = os.path.join(current_dir, '..', 'services')
    if services_dir not in sys.path:
        sys.path.insert(0, services_dir)

    try:
        # Search USDA database (cached for 30 days)
        foods = usda_api.search_foods(query, page_size=10, use_cache=True)

        # Get all allergens for detection
        all_allergens = Allergen.objects.all()

        # Format results for frontend
        results = []
        for food in foods:
            name = food.get('description', '')
            brand = food.get('brandOwner', '') or 'Generic'

            # Extract calories
            calories = next(
                (nutrient.get("value", 0) for nutrient in food.get("foodNutrients", [])
                 if nutrient.get("nutrientName") == "Energy"),
                0
            )

            # Detect potential allergens from ingredient name
            detected_allergens = detect_allergens_from_name(name, all_allergens)

            results.append({
                'name': name,
                'brand': brand,
                'calories': int(calories) if calories else 0,
                'fdc_id': food.get('fdcId', ''),
                'data_type': food.get('dataType', ''),
                'suggested_allergens': [
                    {
                        'id': allergen.id, 
                        'name': allergen.name, 
                        'category': allergen.category
                    }
                    for allergen in detected_allergens
                ]
            })

        return JsonResponse({'results': results})

    except ImportError as e:
        return JsonResponse({
            'error': f'USDA API module not available: {str(e)}'
        }, status=500)
    except (ValueError, KeyError, TypeError) as e:
        return JsonResponse({
            'error': f'Failed to search USDA database: {str(e)}'
        }, status=500)
    except Exception as e:  # pylint: disable=broad-except
        return JsonResponse({
            'error': f'Failed to search USDA database: {str(e)}'
        }, status=500)

def detect_allergens_from_name(ingredient_name, allergen_objects):
    """
    Detect potential allergens in an ingredient based on name matching.

    Uses both the main allergen name and alternative names for matching.

    Args:
        ingredient_name: Name of the ingredient to check
        allergen_objects: QuerySet or list of Allergen objects from database

    Returns:
        List of Allergen objects that match
    """
    ingredient_lower = ingredient_name.lower()
    detected_allergens = []

    for allergen in allergen_objects:
        # Check main name
        if allergen.name.lower() in ingredient_lower:
            if allergen not in detected_allergens:
                detected_allergens.append(allergen)
            continue

        # Check alternative names
        for alt_name in allergen.alternative_names:
            if alt_name.lower() in ingredient_lower:
                if allergen not in detected_allergens:
                    detected_allergens.append(allergen)
                break

    return detected_allergens

def _get_client_ip(request):
    """Extract client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@require_http_methods(["POST"])
@login_required
def scan_pantry(request):
    """
    Scan pantry image and extract ingredients using GPT-4 Vision.
    
    Endpoint: POST /api/pantry/scan/
    
    Request (multipart/form-data):
        - image: Image file (jpg, png, gif)
        
    Response (JSON):
        {
            "success": true,
            "detected_ingredients": [
                {
                    "name": "Chicken Breast",
                    "brand": "Generic",
                    "calories": 165,
                    "allergens": ["..."],
                    "validation_status": "success",
                    "validation_notes": "..."
                }
            ],
            "duplicates_removed": 2,
            "scans_remaining": 4,
            "total_detected": 10
        }
    """
    logger.info("Pantry scan request from user: %s", request.user.username)

    # Check rate limit
    is_allowed, scans_remaining, reset_time = ScanRateLimit.check_rate_limit(
        request.user,
        max_scans=5,
        time_window_minutes=5
    )

    if not is_allowed:
        logger.warning("Rate limit exceeded for user: %s", request.user.username)
        reset_minutes = (reset_time - timezone.now()).seconds // 60
        return JsonResponse({
            'success': False,
            'error': 'Rate limit exceeded',
            'message': (
                f'You have reached the maximum of 5 scans per 5 minutes.'
                f'Please try again in {reset_minutes} minute(s).'
            ),
            'scans_remaining': 0,
            'reset_time': reset_time.isoformat() if reset_time else None
        }, status=429)

    # Validate image file
    if 'image' not in request.FILES:
        logger.error("No image file provided")
        return JsonResponse({
            'success': False,
            'error': 'No image file provided'
        }, status=400)

    image_file = request.FILES['image']

    # Validate file type
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/jpg']
    if image_file.content_type not in allowed_types:
        logger.error("Invalid file type: %s", image_file.content_type)
        return JsonResponse({
            'success': False,
            'error': 'Invalid file type. Please upload a JPG, PNG, or GIF image.'
        }, status=400)

    # Validate file size (5MB limit)
    max_size = 5 * 1024 * 1024  # 5MB
    if image_file.size > max_size:
        logger.error("File too large: %s bytes", image_file.size)
        return JsonResponse({
            'success': False,
            'error': 'File too large. Maximum size is 5MB.'
        }, status=400)

    try:
        # Convert image to base64
        image_data = image_file.read()
        base64_image = base64.b64encode(image_data).decode('utf-8')

        # Determine image mime type
        mime_type = image_file.content_type

        # Call GPT-4 Vision API
        logger.info("Calling GPT-4 Vision API")
        detected_ingredients = _call_gpt_vision(base64_image, mime_type)

        if not detected_ingredients:
            logger.warning("No ingredients detected by GPT-4 Vision")
            return JsonResponse({
                'success': True,
                'detected_ingredients': [],
                'duplicates_removed': 0,
                'scans_remaining': scans_remaining - 1,
                'total_detected': 0,
                'message': 'No ingredients detected. The image may be too blurry or unclear.'
            })

        logger.info("GPT-4 detected %s ingredients", len(detected_ingredients))

        # Validate ingredients with USDA
        logger.info("Validating ingredients with USDA API")
        usda_api_key = os.getenv('USDA_API_KEY')
        validator = USDAIngredientValidator(usda_api_key)
        validated_ingredients = validator.validate_ingredients(detected_ingredients)

        # Deduplicate against existing pantry
        unique_ingredients, duplicates_count = _deduplicate_pantry_ingredients(
            request.user,
            validated_ingredients
        )

        logger.info("Removed %s duplicates", duplicates_count)

        # Record scan attempt
        ScanRateLimit.record_scan(request.user, _get_client_ip(request))

        return JsonResponse({
            'success': True,
            'detected_ingredients': unique_ingredients,
            'duplicates_removed': duplicates_count,
            'scans_remaining': scans_remaining - 1,
            'total_detected': len(detected_ingredients)
        })

    except json.JSONDecodeError as e:
        logger.error("JSON decode error: %s", str(e))
        return JsonResponse({
            'success': False,
            'error': 'Failed to parse GPT-4 response'
        }, status=500)
    except RequestException as e:
        logger.error("API request failed: %s", str(e))
        return JsonResponse({
            'success': False,
            'error': 'API request failed. Please try again.'
        }, status=500)
    except Timeout:
        logger.error("API timeout")
        return JsonResponse({
            'success': False,
            'error': 'Request timed out. Please try again.'
        }, status=504)
    except Exception as e:
        logger.error("Unexpected error during scan: %s", str(e))
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred. Please try again.'
        }, status=500)

def _call_gpt_vision(base64_image: str, mime_type: str) -> List[str]:
    """
    Call GPT-4 Vision API to extract ingredients from image.
    
    Args:
        base64_image: Base64-encoded image data
        mime_type: MIME type of the image
        
    Returns:
        List of ingredient names detected
    """
    api_key = os.getenv('OPENAI_API_KEY')

    if not api_key:
        raise ValueError("OpenAI API key not found")

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",  # or "gpt-4o"
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """You are a pantry scanning assistant. 
Analyze this image of a pantry or refrigerator and list all visible food items and ingredients.

Rules:
1. Return ONLY a JSON array of ingredient names
2. Include brand names if visible (e.g., "Jif Peanut Butter")
3. Be specific (e.g., "Chicken Breast" not just "Chicken")
4. Only include items you can clearly identify
5. Skip condiments, spices, and tiny items
6. Do not include any explanatory text, only the JSON array

Example output format:
["Chicken Breast", "Cheddar Cheese", "Whole Milk", "Banana", "Brown Rice"]
"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}",
                                "detail": "low"  # Cost optimization
                            }
                        }
                    ]
                }
            ],
            max_tokens=500,
            temperature=0.3
        )

        content = response.choices[0].message.content

        # Clean up response (same as before)
        content = content.strip()
        if content.startswith("```"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        ingredients = json.loads(content)
        if not isinstance(ingredients, list):
            logger.error("GPT-4 returned non-list response: %s", type(ingredients))
            return []

        logger.info("GPT-4 successfully extracted %s ingredients", len(ingredients))
        return ingredients

    except Exception as e:
        logger.error("GPT-4 API request failed: %s", str(e))
        raise

def _deduplicate_pantry_ingredients(
    user,
    validated_ingredients: List[Dict]
) -> tuple:
    """
    Remove ingredients that already exist in user's pantry.
    
    Args:
        user: User object
        validated_ingredients: List of validated ingredient dicts
        
    Returns:
        Tuple of (unique_ingredients, duplicates_count)
    """
    # Get user's existing pantry ingredients
    pantry, _ = Pantry.objects.get_or_create(user=user)
    existing_ingredients = pantry.ingredients.all()

    # Create set of existing ingredient names (case-insensitive)
    existing_names = {
        f"{ing.name.lower()}|{ing.brand.lower()}"
        for ing in existing_ingredients
    }

    unique_ingredients = []
    duplicates_count = 0

    for ingredient in validated_ingredients:
        key = f"{ingredient['name'].lower()}|{ingredient['brand'].lower()}"

        if key not in existing_names:
            unique_ingredients.append(ingredient)
        else:
            duplicates_count += 1
            logger.debug("Duplicate found: %s", ingredient['name'])

    return unique_ingredients, duplicates_count

@require_http_methods(["POST"])
@login_required
def add_scanned_ingredients(request):
    """
    Add confirmed scanned ingredients to user's pantry.

    Endpoint: POST /api/pantry/add-scanned/

    Request (JSON):
        {
            "ingredients": [
                {
                    "name": "Chicken Breast",
                    "brand": "Generic",
                    "calories": 165,
                    "allergens": ["..."]
                }
            ]
        }

    Response (JSON):
        {
            "success": true,
            "added_count": 5,
            "ingredients": [...]
        }
    """
    logger.info("Add scanned ingredients request from user: %s", request.user.username)

    try:
        data = json.loads(request.body)
        ingredients_data = data.get('ingredients', [])

        if not ingredients_data:
            return JsonResponse({
                'success': False,
                'error': 'No ingredients provided'
            }, status=400)

        added_ingredients = []
        allergen_cache = {}  # Cache allergen lookups

        for ing_data in ingredients_data:
            try:
                # Get or create ingredient
                ingredient, created = Ingredient.objects.get_or_create(
                    name=ing_data['name'],
                    brand=ing_data.get('brand', 'Generic'),
                    defaults={
                        'calories': ing_data.get('calories', 0)
                    }
                )

                # Update calories if ingredient existed but has different value
                if not created and ingredient.calories != ing_data.get('calories', 0):
                    ingredient.calories = ing_data.get('calories', 0)
                    ingredient.save()

                # Add allergens
                allergen_names = ing_data.get('allergens', [])
                if allergen_names:
                    allergens = []
                    for allergen_name in allergen_names:
                        # Use cache to avoid duplicate DB queries
                        if allergen_name not in allergen_cache:
                            allergen, _ = Allergen.objects.get_or_create(
                                name=allergen_name,
                                defaults={'category': 'fda_major_9'}
                            )
                            allergen_cache[allergen_name] = allergen
                        allergens.append(allergen_cache[allergen_name])

                    ingredient.allergens.set(allergens)

                # Add to user's pantry
                pantry, _ = Pantry.objects.get_or_create(user=request.user)

                if ingredient not in pantry.ingredients.all():
                    pantry.ingredients.add(ingredient)
                    added_ingredients.append({
                        'id': ingredient.id,
                        'name': ingredient.name,
                        'brand': ingredient.brand,
                        'calories': ingredient.calories
                    })

            except Exception as e:
                logger.error("Error adding ingredient %s: %s", ing_data.get('name'), str(e))
                continue

        logger.info("Added %s ingredients to pantry", len(added_ingredients))

        return JsonResponse({
            'success': True,
            'added_count': len(added_ingredients),
            'ingredients': added_ingredients
        })

    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error("Error adding scanned ingredients: %s", str(e))
        return JsonResponse({
            'success': False,
            'error': 'Failed to add ingredients'
        }, status=500)
