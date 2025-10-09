from django.shortcuts import render
from rest_framework import viewsets

from .models import Pantry, Ingredient
from .serializers import IngredientSerializer, PantrySerializer

def index(request):
    return render(request, 'index.html')

def pantry(request):
    """Pantry View"""
    pantry = Pantry.objects.all()
    return render(request, 'pantry.html', {'pantry': pantry})

def recipeSearch(request):
    return render(request, 'recipe-search.html')

def addRecipe(request):
    return render(request, 'add-recipe.html')