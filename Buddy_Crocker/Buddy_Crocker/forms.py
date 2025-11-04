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

    Allows users to input ingredient name, brand, calorie count, and allergen selections.
    """
<<<<<<< HEAD
    class Meta:
        model = Ingredient
        fields = ["name", "calories"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Ground Beef"}),
=======
    allergens = forms.ModelMultipleChoiceField(
        queryset=Allergen.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select all allergens present in this ingredient"
    )
    
    brand = forms.CharField(
        required=False,
        initial='Generic',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Jif, Skippy, Organic Valley, or leave as Generic'
        }),
        help_text='Specify brand for branded products, or leave as "Generic" for whole foods'
    )

    class Meta:
        model = Ingredient
        fields = ['name', 'brand', 'calories', 'allergens']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter ingredient name'
            }),
            'calories': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter the calorie count'
            }),
>>>>>>> development
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
    
    def clean_brand(self):
        """Validate and normalize brand field."""
        brand = self.cleaned_data.get('brand', '').strip()
        if not brand:
            brand = 'Generic'
        return brand
    
    def clean_calories(self):
        """Validate that calories are not empty"""
        calories = self.cleaned_data.get('calories')
        if not calories:
            raise forms.ValidationError("Calories cannot be empty")
        return calories

    


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
<<<<<<< HEAD
=======

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
>>>>>>> development
