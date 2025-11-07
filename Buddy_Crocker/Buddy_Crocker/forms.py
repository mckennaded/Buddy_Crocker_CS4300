"""
Forms for Buddy Crocker meal planning and recipe management app.

This module defines forms for user input and data validation.
"""
from django import forms
from .models import Recipe, Ingredient, Profile, Allergen
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _

from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Ingredient, Allergen

class IngredientForm(forms.ModelForm):
    # M2M allergens with checkboxes
    allergens = forms.ModelMultipleChoiceField(
        queryset=Allergen.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text=_("Select all allergens present in this ingredient"),
    )

    # Brand (only if your model has it)
    brand = forms.CharField(
        required=False,
        initial="Generic",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": 'e.g., Jif, Skippy, Organic Valley, or leave as "Generic"',
        }),
        help_text=_('Specify brand, or leave as "Generic" for whole foods'),
    )

    class Meta:
        model = Ingredient
        fields = ["name", "brand", "calories", "allergens"]  # include "brand" only if it exists on the model
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter ingredient name",
            }),
            "calories": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Enter the calorie count",
            }),
        }
        error_messages = {
            "name": {
                "required": _("Please enter an ingredient name."),
                "max_length": _("That name is too long."),
            },
        }

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise forms.ValidationError(_("Please enter an ingredient name."))
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
        error_messages = {
            "title": {
                "required": _("Please enter a title for your recipe."),
                "max_length": _("That title is a bit long—try shortening it."),
            },
            "instructions": {
                "required": _("Write a few steps so people can make it."),
            },
        }
        help_texts = {
            'title': 'Give your recipe a descriptive title',
            'instructions': 'Provide clear, step-by-step cooking instructions',
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

