"""
Forms for Buddy Crocker meal planning and recipe management app.

This module defines forms for user input and data validation.
"""
from django import forms
from .models import Recipe, Ingredient


class RecipeForm(forms.ModelForm):
    """
    Form for creating and editing recipes.
    
    Allows users to input recipe title, instructions, and select ingredients.
    """
    
    ingredients = forms.ModelMultipleChoiceField(
        queryset=Ingredient.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select ingredients used in this recipe"
    )
    
    class Meta:
        model = Recipe
        fields = ['title', 'instructions', 'ingredients']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter recipe title'
            }),
            'instructions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Enter step-by-step instructions'
            }),
        }
        help_texts = {
            'title': 'Give your recipe a descriptive title',
            'instructions': 'Provide clear, step-by-step cooking instructions',
        }
    
    def clean_title(self):
        """Validate that title is not empty and strip whitespace."""
        title = self.cleaned_data.get('title')
        if title:
            title = title.strip()
            if not title:
                raise forms.ValidationError("Title cannot be empty or just whitespace.")
        return title
    
    def clean_instructions(self):
        """Validate that instructions are not empty and strip whitespace."""
        instructions = self.cleaned_data.get('instructions')
        if instructions:
            instructions = instructions.strip()
            if not instructions:
                raise forms.ValidationError("Instructions cannot be empty or just whitespace.")
        return instructions