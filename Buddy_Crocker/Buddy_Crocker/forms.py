"""
Forms for Buddy Crocker meal planning and recipe management app.

This module defines forms for user input and data validation.
"""
from django import forms
from .models import Recipe, Ingredient



class IngredientForm(forms.ModelForm):
    """
    Form for creating and editing ingredients

    Allows users to input ingredient name, calorie count, and alergy triggers. 
    """
    class Meta:
        model = Ingredient
        fields = ["name", "calories"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Ground Beef"}),
        }
    # class Meta:
    #     model = Ingredient
    #     fields = ['name', 'calories', 'allergens']
    #     widgets = {
    #         'name': forms.TextInput(attrs={
    #             'class': 'form-control',
    #             'placeholder': 'Enter ingredient name'
    #         }),
    #         'calories': forms.NumberInput(attrs={
    #             'class': 'form-control',
    #             'placeholder': 'Enter the calorie count'
    #         }),
    #         'allergens': forms.TextInput(attrs={
    #             'class': 'form-control',
    #             'placeholder': 'Enter the allergens'
    #         })
    #     }
    
    def clean_name(self):
        """Validate that name is not empty and strip whitespace."""
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
            if not name:
                raise forms.ValidationError("Name cannot be empty or just whitespace.")
        return name
    
    def clean_calories(self):
        """Validate that calories are not empty"""
        calories = self.cleaned_data.get('calories')
        if not calories:
            raise forms.ValidationError("Calories cannot be empty")
        return calories

    def clean_allergens(self):
        """Validate that allergens are not empty and strip whitespace."""
        allergens = self.cleaned_data.get('allergens')
        if allergens:
            allergens = allergens.strip()
            #if not allergens:
                #raise forms.ValidationError("Allergens cannot be empty or just whitespace.")
        return allergens
    


class RecipeForm(forms.ModelForm):
    ingredients = forms.CharField(
        label="Ingredients",
        widget=forms.Textarea(attrs={
            "rows": 4,
            "placeholder": "List ingredients, one per line or comma-separated",
            "class": "form-control",
        }),
        required=False,
        help_text="Example: Ground beef, Onion, Cumin, Beans",
    )

    class Meta:
        model = Recipe
        fields = ["title", "ingredients", "instructions"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter recipe title",
            }),
            "instructions": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 6,
                "placeholder": "Enter step-by-step instructions",
            }),
        }

    def clean_title(self):
        """Validate that title is not empty and strip whitespace."""
        title = self.cleaned_data.get('title', '').strip()
        if not title:
            raise forms.ValidationError("Title cannot be empty or just whitespace.")
        return title

    def clean_instructions(self):
        """Validate that instructions are not empty and strip whitespace."""
        instructions = self.cleaned_data.get('instructions', '').strip()
        if not instructions:
            raise forms.ValidationError("Instructions cannot be empty or just whitespace.")
        return instructions
