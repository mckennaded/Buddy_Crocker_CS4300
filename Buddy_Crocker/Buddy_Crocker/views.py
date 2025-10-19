"""
Views for Buddy Crocker meal planning and recipe management app.

This module defines all view functions for handling HTTP requests
and rendering templates.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from .models import Allergen, Ingredient, Recipe, Pantry, Profile
from .forms import RecipeForm, IngredientForm



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
    return render(request, 'Buddy_Crocker/recipe_search.html', context)


# views.py  — replace your recipeDetail with this
from django.shortcuts import get_object_or_404, render
from .models import Recipe

def recipeDetail(request, pk):
    """
    Public recipe detail that discovers ingredients regardless of schema and
    computes allergens without calling Recipe.get_allergens().
    """
    recipe = get_object_or_404(Recipe, pk=pk)

    # ---- Discover ingredients no matter how they're related ----
    def get_ingredients(rec):
        # 1) Direct M2M on Recipe: rec.ingredients
        if hasattr(rec, "ingredients"):
            try:
                return list(rec.ingredients.all())
            except Exception:
                pass
        # 2) FK on Ingredient to Recipe: rec.ingredient_set
        if hasattr(rec, "ingredient_set"):
            try:
                return list(rec.ingredient_set.all())
            except Exception:
                pass
        # 3) Through model RecipeIngredient -> Ingredient: rec.recipeingredient_set
        if hasattr(rec, "recipeingredient_set"):
            try:
                ris = rec.recipeingredient_set.select_related("ingredient").all()
                return [ri.ingredient for ri in ris if getattr(ri, "ingredient", None)]
            except Exception:
                pass
        # 4) Fallback: scan reverse relations for an Ingredient-like model
        for f in rec._meta.get_fields():
            rel = getattr(f, "related_model", None)
            if not rel:
                continue
            if rel.__name__.lower() == "ingredient":
                accessor = f.get_accessor_name()
                mgr = getattr(rec, accessor, None)
                if mgr:
                    try:
                        qs = mgr.all()
                        if qs and qs.model.__name__.lower() == "ingredient":
                            return list(qs)
                        mapped = []
                        for obj in qs:
                            ing = getattr(obj, "ingredient", None)
                            if ing:
                                mapped.append(ing)
                        if mapped:
                            return mapped
                    except Exception:
                        continue
        return []

    ingredients = get_ingredients(recipe)

    # ---- Collect allergens from ingredients (works for M2M or text) ----
    allergen_labels = set()
    for ing in ingredients:
        alls = getattr(ing, "allergens", None)
        if not alls:
            continue
        if hasattr(alls, "all"):  # ManyToMany to Allergen
            try:
                for a in alls.all():
                    name = (str(a) or "").strip()
                    if name:
                        allergen_labels.add(name)
            except Exception:
                pass
        else:  # Text/Char field
            txt = (str(alls) or "").strip()
            if txt:
                for part in txt.replace(";", ",").split(","):
                    name = part.strip()
                    if name:
                        allergen_labels.add(name)

    # ---- User conflict (robust to M2M or text on Profile) ----
    allergen_warning = False
    if request.user.is_authenticated:
        profile = getattr(request.user, "profile", None)
        if profile:
            u_all = getattr(profile, "allergens", None)
            user_labels = set()
            if u_all and hasattr(u_all, "all"):   # M2M on profile
                try:
                    user_labels = { (str(a) or "").strip()
                                    for a in u_all.all() if (str(a) or "").strip() }
                except Exception:
                    user_labels = set()
            else:  # text on profile
                txt = (str(u_all) or "").strip()
                if txt:
                    user_labels = { p.strip()
                                    for p in txt.replace(";", ",").split(",")
                                    if p.strip() }
            if user_labels & allergen_labels:
                allergen_warning = True

    context = {
        "recipe": recipe,
        "ingredients": ingredients,                                # use this in template
        "recipe_allergens": sorted(allergen_labels, key=str.lower),
        "allergen_warning": allergen_warning,
    }
    return render(request, "Buddy_Crocker/recipe_detail.html", context)    


def ingredientDetail(request, pk):
    """
    Display detailed information about a specific ingredient.
    
    Public view accessible to all users.
    
    Args:
        pk: Primary key of the ingredient
    """
    ingredient = get_object_or_404(Ingredient, pk=pk)
    
    # Get recipes using this ingredient
    related_recipes = ingredient.recipes.all()
    
    context = {
        'ingredient': ingredient,
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
    
    context = {
        'allergen': allergen,
        'affected_ingredients': affected_ingredients,
        'affected_recipes': affected_recipes,
    }
    return render(request, 'Buddy_Crocker/allergen_detail.html', context)


# @login_required
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

# @login_required
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

    return render(request, "Buddy_Crocker/add_recipe.html", {"form": form})
# @login_required
def profileDetail(request, pk):
    """
    Display and manage a user's profile.
    
    Login required view. Users can only view/edit their own profile.
    
    Args:
        pk: Primary key of the user whose profile to display
    """
    # Ensure user can only access their own profile
    if request.user.pk != pk:
        return redirect('profile-detail', pk=request.user.pk)
    
    user = get_object_or_404(User, pk=pk)
    
    # Get or create profile for user
    profile, created = Profile.objects.get_or_create(user=user)
    
    # Handle POST request to add/remove allergens
    if request.method == 'POST':
        action = request.POST.get('action')
        allergen_id = request.POST.get('allergen_id')
        
        if allergen_id:
            allergen = get_object_or_404(Allergen, pk=allergen_id)
            
            if action == 'add':
                profile.allergens.add(allergen)
            elif action == 'remove':
                profile.allergens.remove(allergen)
        
        return redirect('profile-detail', pk=pk)
    
    # Get all allergens for selection
    all_allergens = Allergen.objects.all()
    profile_allergen_ids = set(profile.allergens.values_list('id', flat=True))
    
    # Get safe recipes for this user
    safe_recipes = profile.get_safe_recipes()[:10]  # Limit to 10
    
    context = {
        'profile': profile,
        'all_allergens': all_allergens,
        'profile_allergen_ids': profile_allergen_ids,
        'safe_recipes': safe_recipes,
    }
    return render(request, 'Buddy_Crocker/profile_detail.html', context)

