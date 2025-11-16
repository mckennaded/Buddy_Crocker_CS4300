"""
admin.py allows admin access to the included models
"""
from django.contrib import admin
from .models import Allergen, Recipe, Ingredient, Pantry, Profile

admin.site.register([Allergen, Recipe, Ingredient, Pantry, Profile])
