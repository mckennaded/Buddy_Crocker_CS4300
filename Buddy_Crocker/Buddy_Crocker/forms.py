"""
Forms for Buddy Crocker meal planning and recipe management app.

This module defines forms for user input and data validation.
"""
from django import forms
from .models import Recipe, Ingredient, Profile, Allergen
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

class IngredientForm(forms.ModelForm):
    """
    Form for creating and editing ingredients

    Allows users to input ingredient name, calorie count, and alergy triggers. 
    """
    allergens = forms.ModelMultipleChoiceField(
        queryset=Allergen.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select all allergens present in this ingredient"
    )

    class Meta:
        model = Ingredient
        fields = ['name', 'calories', 'allergens']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter ingredient name'
            }),
            'calories': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter the calorie count'
            })
        }
    
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
        fields = ['title', 'instructions']   #, 'ingredients']
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

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username']

class ProfileForm(forms.ModelForm):
    allergens = forms.ModelMultipleChoiceField(
        queryset=Allergen.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    class Meta:
        model = Profile
        fields = ['allergens']



class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(required=True, widget=forms.TextInput(attrs={'class':'form-control'}))
    last_name = forms.CharField(required=True, widget=forms.TextInput(attrs={'class':'form-control'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class':'form-control'}))
    allergens = forms.ModelMultipleChoiceField(
        queryset=Allergen.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            profile, created = Profile.objects.get_or_create(user=user)
            allergens = self.cleaned_data.get('allergens')
            if allergens:
                profile.allergens.set(allergens)
                profile.save()
        return user
