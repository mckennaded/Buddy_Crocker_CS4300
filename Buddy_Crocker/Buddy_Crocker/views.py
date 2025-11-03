"""
Views for Buddy Crocker meal planning and recipe management app.

This module defines all view functions for handling HTTP requests
and rendering templates.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.db import IntegrityError
from .models import Allergen, Ingredient, Recipe, Pantry, Profile
from .forms import RecipeForm, IngredientForm, UserForm, ProfileForm
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login, logout
from django.contrib.auth.views import LoginView
from django.urls import reverse
from .forms import CustomUserCreationForm
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


@require_POST
@csrf_exempt
def custom_logout(request):
    logout(request)
    return redirect("login")



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
    
    Public view accessible to all users.
    """
    recipe = get_object_or_404(Recipe, pk=pk)
    
    # Get all ingredients for this recipe
    ingredients = recipe.ingredients.all()
    
    # Get all allergens from ingredients
    recipe_allergens = recipe.get_allergens()
    
    # Check if user has allergen conflicts
    allergen_warning = False
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            user_allergens = set(profile.allergens.all())
            if user_allergens & set(recipe_allergens):
                allergen_warning = True
        except Profile.DoesNotExist:
            pass
    
    context = {
        'recipe': recipe,
        'ingredients': ingredients,
        'recipe_allergens': recipe_allergens,
        'allergen_warning': allergen_warning,
    }
    return render(request, 'Buddy_Crocker/recipe_detail.html', context)


def ingredientDetail(request, pk):
    """
    Display detailed information about a specific ingredient.
    
    Public view accessible to all users.
    
    Args:
        pk: Primary key of the ingredient
    """
    ingredient = get_object_or_404(Ingredient, pk=pk)
    
    # Get allergens for this ingredient
    allergens = ingredient.allergens.all()

    # Get recipes using this ingredient
    related_recipes = ingredient.recipes.all()
    
    context = {
        'ingredient': ingredient,
        'allergens': allergens,
        'related_recipes': related_recipes,
    }
    return render(request, 'Buddy_Crocker/ingredient_detail.html', context)


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
    Display and manage the user's pantry.
    
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
    
    # Get all ingredients for adding to pantry
    all_ingredients = Ingredient.objects.all()
    pantry_ingredient_ids = set(pantry_obj.ingredients.values_list('id', flat=True))
    
    context = {
        'pantry': pantry_obj,
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
            ingredient = form.save(commit=False)
            ingredient.save()
            form.save_m2m()  # Save many-to-many relationships

            #Add the ingredient to the pantry
            pantry_obj, created = Pantry.objects.get_or_create(user=request.user)
            pantry_obj.ingredients.add(ingredient)

            #Show the details page
            return redirect('ingredient-detail', pk=ingredient.pk)
    else:
        form = IngredientForm()
    
    context = {
        'form': form,
    }
    return render(request, 'Buddy_Crocker/add-ingredient.html', context)

@login_required
def addRecipe(request):
    if request.method == "POST":
        form = RecipeForm(request.POST)
        if form.is_valid():
            title = (form.cleaned_data.get("title") or "").strip()

            # 1) Prevent duplicate title for this author (case-insensitive)
            if Recipe.objects.filter(author=request.user, title__iexact=title).exists():
                form.add_error("title", "You already have a recipe with this title. Choose a different title.")
                return render(request, "Buddy_Crocker/add_recipe.html", {"form": form})

            # 2) Save safely (guard against race-condition IntegrityError)
            recipe = form.save(commit=False)
            recipe.author = request.user
            try:
                recipe.save()
                form.save_m2m()
                return redirect("recipe-detail", pk=recipe.pk)
            except IntegrityError:
                form.add_error("title", "You already have a recipe with this title. Choose a different title.")
                return render(request, "Buddy_Crocker/add_recipe.html", {"form": form})
        else:
            # form errors (e.g., missing fields) will render below
            pass
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
