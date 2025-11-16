# pylint: disable=too-few-public-methods
"""
Django REST Framework serializers for pantry management and ingredient tracking.

Serializers:
    IngredientSerializer: Serializes individual ingredient data including name,
        calories, and associated allergens.
    PantrySerializer: Serializes pantry data with associated user and ingredients list.

Usage:
    Used in views to serialize/deserialize model data for API requests/responses.
"""
#Imports
from rest_framework import serializers
from .models import Pantry, Ingredient

#Ingredient Serializer
class IngredientSerializer(serializers.ModelSerializer):
    """
    Serializer for Ingredient model instances.
    """
    class Meta:
        model = Ingredient
        fields = ['name', 'calories', 'allergens']

#Pantry Serializer
class PantrySerializer(serializers.ModelSerializer):
    """
    Serializer for Pantry model instances.
    """
    class Meta:
        model = Pantry
        fields = ['user', 'ingredients']
