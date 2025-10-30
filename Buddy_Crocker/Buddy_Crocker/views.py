"""
Views for Buddy Crocker meal planning and recipe management app.

This module defines all view functions for handling HTTP requests
and rendering templates.
"""
# Django imports
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.db import IntegrityError
from .models import Allergen, Ingredient, Recipe, Pantry, Profile
from .forms import RecipeForm, IngredientForm, UserForm, ProfileForm
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login, logout
from django.contrib.auth.views import LoginView
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.utils.http import urlencode


# Project imports
from .forms import CustomUserCreationForm, IngredientForm, ProfileForm, RecipeForm, UserForm
from .models import Allergen, Ingredient, Pantry, Profile, Recipe


@require_POST
@login_required
def custom_logout(request):
    logout(request)
    return redirect("login")


def trigger_error(request):
    1 / 0  # force a server error

class CustomLoginView(LoginView):
    def get_success_url(self):
        return reverse('profile-detail', kwargs={'pk': self.request.user.pk})


# User Registry
def register(request):
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
    return render(request, 'Buddy_Crocker/index.html', context)



def recipeSearch(request):
    """
    Display recipe search/browse page with optional filtering.
    
    Public view accessible to all users.
    Query parameters:
        - q: Search query for recipe title
        - exclude_allergens: List of allergen IDs to exclude
    """
    recipes = Recipe.objects.all()
    
    # Search by title
    search_query = request.GET.get('q', '')
    if search_query:
        recipes = recipes.filter(title__icontains=search_query)
    
    # Filter by allergens (exclude recipes with specified allergens)
    exclude_allergens = request.GET.getlist('exclude_allergens')
    if exclude_allergens:
        # Get recipes that contain ingredients with excluded allergens
        recipes_with_allergens = Recipe.objects.filter(
            ingredients__allergens__id__in=exclude_allergens
        ).distinct()
        
        # Exclude those recipes
        recipes = recipes.exclude(id__in=recipes_with_allergens)
    
    # Get all allergens for filter form
    all_allergens = Allergen.objects.all()
    
    # If user is logged in, pre-select their profile allergens
    selected_allergens = []
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            selected_allergens = list(profile.allergens.values_list('id', flat=True))
        except Profile.DoesNotExist:
            pass
    
    context = {
        'recipes': recipes,
        'all_allergens': all_allergens,
        'selected_allergens': selected_allergens,
        'search_query': search_query,
    }
    return render(request, 'Buddy_Crocker/recipe-search.html', context)


def recipeDetail(request, pk):
    """
    Display detailed information about a specific recipe.
    
    Shows personalized allergen warnings based on user's profile.
    - Authenticated users with allergen preferences: Only see their allergens
    - Authenticated users without preferences: No warnings shown
    - Unauthenticated users: See all allergens (safety first)
    
    Public view accessible to all users.
    """
    recipe = get_object_or_404(Recipe, pk=pk)
    
    # Get all ingredients for this recipe
    ingredients = recipe.ingredients.all()
    
    # Get all allergens from ingredients
    all_recipe_allergens = recipe.get_allergens()
    
    # Personalize allergen display based on user profile
    user_allergens = []
    relevant_allergens = []
    has_allergen_conflict = False
    is_safe_for_user = False
    show_all_allergens = True  # Default for non-authenticated users
    
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            user_allergens = list(profile.allergens.all())
            
            if user_allergens:
                # User has allergen preferences - show only relevant ones
                show_all_allergens = False
                relevant_allergens = [a for a in all_recipe_allergens if a in user_allergens]
                has_allergen_conflict = len(relevant_allergens) > 0
                is_safe_for_user = len(relevant_allergens) == 0
            else:
                # User has no allergen preferences - don't show warnings
                show_all_allergens = False
                is_safe_for_user = True
                
        except Profile.DoesNotExist:
            # No profile - show all allergens for safety
            show_all_allergens = True
    
    context = {
        'recipe': recipe,
        'ingredients': ingredients,
        'all_recipe_allergens': all_recipe_allergens,  # All allergens in recipe
        'relevant_allergens': relevant_allergens,  # Only user's allergens
        'user_allergens': user_allergens,  # User's allergen preferences
        'has_allergen_conflict': has_allergen_conflict,  # User can't eat this
        'is_safe_for_user': is_safe_for_user,  # User can eat this
        'show_all_allergens': show_all_allergens,  # Show all vs personalized
    }
    return render(request, 'Buddy_Crocker/recipe_detail.html', context)


def ingredientDetail(request, pk):
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
    
    # Get all allergens for this ingredient
    all_allergens = ingredient.allergens.all()
    
    # Personalize allergen display based on user profile
    user_allergens = []
    relevant_allergens = []
    has_allergen_conflict = False
    is_safe_for_user = False
    show_all_allergens = True  # Default for non-authenticated users
    
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            user_allergens = list(profile.allergens.all())
            
            if user_allergens:
                # User has allergen preferences - show only relevant ones
                show_all_allergens = False
                relevant_allergens = [a for a in all_allergens if a in user_allergens]
                has_allergen_conflict = len(relevant_allergens) > 0
                is_safe_for_user = len(relevant_allergens) == 0
            else:
                # User has no allergen preferences - don't show warnings
                show_all_allergens = False
                is_safe_for_user = True
                
        except Profile.DoesNotExist:
            # No profile - show all allergens for safety
            show_all_allergens = True
    
    # Get recipes using this ingredient
    related_manager = getattr(ingredient, "recipes", getattr(ingredient, "recipe_set"))
    related_recipes = related_manager.all()

    context = {
        'ingredient': ingredient,
        'all_allergens': all_allergens,  # All allergens in ingredient
        'relevant_allergens': relevant_allergens,  # Only user's allergens
        'user_allergens': user_allergens,  # User's allergen preferences
        'has_allergen_conflict': has_allergen_conflict,  # User can't eat this
        'is_safe_for_user': is_safe_for_user,  # User can eat this
        'show_all_allergens': show_all_allergens,  # Show all vs personalized
        'related_recipes': related_recipes,
    }
    return render(request, "Buddy_Crocker/ingredient_detail.html", context)


def allergenDetail(request, pk):
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
    return render(request, 'Buddy_Crocker/allergen_detail.html', context)


@login_required
def pantry(request):
    """
    Display and manage the user's pantry with personalized allergen warnings.
    
    Shows allergen warnings only for ingredients containing user's allergens.
    Categorizes ingredients as safe/unsafe based on user profile.
    
    Login required view.
    """
    # Get or create pantry for user
    pantry_obj, created = Pantry.objects.get_or_create(user=request.user)
    
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
    
    # Personalize allergen display based on user profile
    user_allergens = []
    safe_ingredients = []
    unsafe_ingredients = []
    show_allergen_warnings = False
    
    try:
        profile = request.user.profile
        user_allergens = list(profile.allergens.all())
        
        if user_allergens:
            show_allergen_warnings = True
            
            # Categorize ingredients
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
        else:
            # User has no allergen preferences - all are safe
            for ingredient in pantry_ingredients:
                ingredient.relevant_allergens = []
                ingredient.has_conflict = False
                ingredient.is_safe = True
                safe_ingredients.append(ingredient)
                
    except Profile.DoesNotExist:
        # No profile - treat all as safe but show all allergens
        for ingredient in pantry_ingredients:
            ingredient.relevant_allergens = list(ingredient.allergens.all())
            ingredient.has_conflict = False
            ingredient.is_safe = True
            safe_ingredients.append(ingredient)
    
    # Get all available ingredients for adding (not used in current template but useful)
    all_ingredients = Ingredient.objects.all()
    pantry_ingredient_ids = set(pantry_obj.ingredients.values_list('id', flat=True))
    
    # Calculate stats
    total_ingredients = pantry_ingredients.count()
    unsafe_count = len(unsafe_ingredients)
    safe_count = len(safe_ingredients)
    
    context = {
        'pantry': pantry_obj,
        'safe_ingredients': safe_ingredients,
        'unsafe_ingredients': unsafe_ingredients,
        'user_allergens': user_allergens,
        'show_allergen_warnings': show_allergen_warnings,
        'total_ingredients': total_ingredients,
        'unsafe_count': unsafe_count,
        'safe_count': safe_count,
        'all_ingredients': all_ingredients,
        'pantry_ingredient_ids': pantry_ingredient_ids,
    }
    return render(request, 'Buddy_Crocker/pantry.html', context)


@login_required
def addIngredient(request):
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
                pantry_obj, created = Pantry.objects.get_or_create(user=request.user)
                
                if not ingredient in pantry_obj.ingredients.all():
                    pantry_obj.ingredients.add(ingredient)
            
            return redirect('ingredient-detail', pk=ingredient.pk)
        messages.error(request, "Please fix the errors below before submitting.")
    else:        
        form = IngredientForm()

    return render(request, 'Buddy_Crocker/add-ingredient.html', {'form': form})

@login_required
def addRecipe(request):
    if request.method == "POST":
        form = RecipeForm(request.POST)
        if form.is_valid():
            title = (form.cleaned_data.get("title") or "").strip()
            # 1) Prevent duplicate title for this author (case-insensitive)
            if Recipe.objects.filter(author=request.user, title__iexact=title).exists():
                form.add_error("title", "You already have a recipe with this title. Choose a different title.")
                messages.error(request, "Please correct the errors below.")
                return render(request, "Buddy_Crocker/add_recipe.html", {"form": form})
            # 2) Save safely (guard against race-condition IntegrityError)
            recipe = form.save(commit=False)
            recipe.author = request.user
            recipe.title = title  # ← save the stripped title
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
                return render(request, "Buddy_Crocker/add_recipe.html", {"form": form})
        else:
            # form errors (e.g., missing fields) will render below before sumbitting")
            messages.error(request,"Please fix the errors below")
    else:
        form = RecipeForm()

    return render(request, 'Buddy_Crocker/add_recipe.html', {'form': form})


@login_required
def profileDetail(request, pk):
    """Display and edit user profile"""
    if request.user.pk != pk:
        return redirect('profile-detail', pk=request.user.pk)

    user = get_object_or_404(User, pk=pk)
    profile, created = Profile.objects.get_or_create(user=user)

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

    # Get safe recipe count
    safe_recipes = profile.get_safe_recipes()
    total_recipes = Recipe.objects.count()

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'user': user,
        'profile': profile,
        'safe_recipe_count': safe_recipes.count(),
        'total_recipe_count': total_recipes,
    }
    return render(request, 'Buddy_Crocker/profile_detail.html', context)

    from django.shortcuts import render

def preview_404(request):
    return render(request, "404.html", status=404)

def preview_500(request):
    return render(request, "500.html", status=500)

from django.shortcuts import render

def page_not_found_view(request, exception, template_name="Buddy_Crocker/404.html"):
    return render(request, template_name, status=404)

def server_error_view(request, template_name="Buddy_Crocker/500.html"):
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
    except Exception as e:
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


