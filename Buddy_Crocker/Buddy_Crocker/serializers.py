#Serializers

#Imports
from rest_framework import Serializers
from .models import Pantry, Ingredient

#Ingredient Serializer
class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ['name', 'calories', 'allergens']

#Pantry Serializer
class PantrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Pantry
        fields = ['user, ingredients']