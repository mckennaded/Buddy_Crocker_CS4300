"""
Forms for Buddy Crocker meal planning and recipe management app.

This module defines forms for user input and data validation.
"""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.forms import inlineformset_factory
from django.forms.models import BaseInlineFormSet
from django.utils.translation import gettext_lazy as _
from .models import Recipe, RecipeIngredient, Ingredient, Profile, Allergen, Pantry

User = get_user_model()

class IngredientForm(forms.ModelForm):
    """
    Form for creating and editing ingredients

    Allows users to input ingredient name, brand, calorie count, and allergen selections.
    """
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
        }
        error_messages = {
            "name": {
                "required": _("Please enter an ingredient name."),
                "max_length": _("That name is too long."),
            },
        }

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
    """Form for creating and editing recipes with metadata."""

    class Meta:
        model = Recipe
        fields = [
            'title',
            'instructions',
            'servings',
            'prep_time',
            'cook_time',
            'difficulty',
            'image',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Grandma\'s Chocolate Chip Cookies'
            }),
            'instructions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': 'Enter step-by-step instructions...'
            }),
            'servings': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'value': '4'
            }),
            'prep_time': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Minutes',
                'min': '0'
            }),
            'cook_time': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Minutes',
                'min': '0'
            }),
            'difficulty': forms.Select(attrs={
                'class': 'form-select'
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }
        help_texts = {
            'servings': 'How many servings does this recipe make?',
            'prep_time': 'Preparation time in minutes (optional)',
            'cook_time': 'Cooking time in minutes (optional)',
            'image': 'Upload a photo of your finished dish (optional)',
        }

    #Only allow users to add ingredients in their pantry to a recipe
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

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

def clean(self):
    """Ensure recipe has valid times and required fields."""
    cleaned_data = super().clean()
    prep_time = cleaned_data.get('prep_time')
    cook_time = cleaned_data.get('cook_time')

    # Convert None to 0 for validation
    prep_time = prep_time or 0
    cook_time = cook_time or 0

    if prep_time < 0 or cook_time < 0:
        raise forms.ValidationError("Prep and cook times cannot be negative.")

    if prep_time > 1440 or cook_time > 1440:  # 24 hours max
        raise forms.ValidationError("Prep/cook times exceed 24 hours.")

    return cleaned_data


class RecipeIngredientForm(forms.ModelForm):
    """Form for individual recipe ingredients with amounts."""

    class Meta:
        model = RecipeIngredient
        fields = ['ingredient', 'amount', 'unit', 'notes']
        widgets = {
            'ingredient': forms.Select(attrs={
                'class': 'form-select ingredient-select'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '1',
                'min': '0.01',
                'step': '0.01'
            }),
            'unit': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'cup, tsp, g, oz',
                'list': 'common-units'
            }),
            'notes': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'chopped, diced, to taste (optional)'
            }),
        }

    def clean(self):
        """Validate amount + unit combination."""
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        unit = cleaned_data.get('unit')

        if amount is not None and amount <= 0:
            raise forms.ValidationError("Amount must be greater than 0.")

        if amount and not unit:
            raise forms.ValidationError("Unit is required when amount is specified.")

        if unit:
            unit = unit.strip().lower()
            if len(unit) < 1:
                raise forms.ValidationError(
                    "Unit must be at least 1 character (e.g., 'g', 'cup', 'tsp')."
                )

        return cleaned_data

    def clean_notes(self):
        """Strip and limit notes length."""
        notes = self.cleaned_data.get('notes', '')
        notes = notes.strip()[:100]
        return notes


class RecipeIngredientFormSetHelper(BaseInlineFormSet):
    """
    Custom inline formset for RecipeIngredient validation.
    
    Ensures at least one valid ingredient entry exists with both amount (>0)
    and unit specified. Used with RecipeIngredientFormSet to enforce recipe
    completeness for Buddy Crocker app. Validates across all forms in the set,
    ignoring deleted entries.
    
    Raises ValidationError if no valid ingredients found.
    """
    def clean(self):
        super().clean()
        has_valid_ingredient = any(
            form.cleaned_data and 
            not form.cleaned_data.get('DELETE') and
            form.cleaned_data.get('amount', 0) > 0 and
            form.cleaned_data.get('unit')
            for form in self.forms
        )
        if not has_valid_ingredient:
            raise forms.ValidationError("At least one ingredient must have amount and unit.")


# Formset for managing multiple ingredients
RecipeIngredientFormSet = inlineformset_factory(
    Recipe,
    RecipeIngredient,
    form=RecipeIngredientForm,
    formset=RecipeIngredientFormSetHelper,
    extra=0,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class UserForm(forms.ModelForm):
    """
    Form for accepting user info
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username']

class ProfileForm(forms.ModelForm):
    """
    Form for choosing allergens in Profile
    """
    allergens = forms.ModelMultipleChoiceField(
        queryset=Allergen.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    class Meta:
        model = Profile
        fields = ['allergens']


class CustomUserCreationForm(UserCreationForm): # pylint: disable=too-many-ancestors
    """
    User registration form
    """
    first_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'class':'form-control'})
    )
    last_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'class':'form-control'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class':'form-control'})
    )
    allergens = forms.ModelMultipleChoiceField(
        queryset=Allergen.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

    def save(self, commit=True):
        """
        Function to save allergens to profile
        """
        user = super().save(commit=commit)
        if commit:
            profile, _created = Profile.objects.get_or_create(user=user)
            allergens = self.cleaned_data.get('allergens')
            if allergens:
                profile.allergens.set(allergens)
                profile.save()
        return user
