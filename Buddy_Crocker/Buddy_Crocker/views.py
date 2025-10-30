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
    ingredient = get_object_or_404(Ingredient, pk=pk)

    # Safely find related recipes
    if hasattr(ingredient, "recipes"):
        related_recipes = ingredient.recipes.all()
    elif hasattr(ingredient, "recipe_set"):
        related_recipes = ingredient.recipe_set.all()
    else:
        related_recipes = Recipe.objects.filter(ingredients=ingredient).distinct()

    context = {
        "ingredient": ingredient,
        "related_recipes": related_recipes,
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
    
    context = {
        'allergen': allergen,
        'affected_ingredients': affected_ingredients,
        'affected_recipes': affected_recipes,
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
            #success banner
            messages.success(request,f"Ingredient '{ingredient.name}' added successfully!")
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

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'user': user,
        'profile': profile,
    }
    return render(request, 'Buddy_Crocker/profile_detail.html', context)

@login_required
def add_recipe_prefill(request, prefill: str):
    text = (prefill or "").strip()
    title = text
    pre_ingredient = None

    # parse "add X to Y" (case-insensitive)
    lower = text.lower()
    if lower.startswith("add "):
        try:
            # split once after "add "
            rest = text[4:]
            left, right = rest.split(" to ", 1)  # keep original case for display
            pre_ingredient = left.strip()
            title = right.strip()
        except ValueError:
            # if it doesn't contain " to ", just fall back to treating whole text as title
            pass

    params = {"title": title}
    if pre_ingredient:
        params["pre_ingredient"] = pre_ingredient

    return redirect(f"{reverse('add-recipe')}?{urlencode(params)}")



def preview_404(request, any=None):
    return render(request, "Buddy_Crocker/404.html", status=404)   

def preview_500(request, any=None):
    return render(request, "Buddy_Crocker/500.html", status=500)   

def page_not_found_view(request, exception, template_name="Buddy_Crocker/404.html"):
    return render(request, template_name, status=404)

def server_error_view(request, template_name="Buddy_Crocker/500.html"):
    return render(request, template_name, status=500)



