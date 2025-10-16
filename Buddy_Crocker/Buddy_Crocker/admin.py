from django.contrib import admin
from .models import Allergen, Recipe, Ingredient, Pantry, Profile

admin.site.register([Allergen, Recipe, Ingredient, Pantry, Profile])
