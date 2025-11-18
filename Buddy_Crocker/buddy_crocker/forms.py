"""Forms for Buddy Crocker application."""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _
from django.apps import apps


# Dynamically get models to avoid pylint no-member false positives
Profile = apps.get_model('buddy_crocker', 'Profile')
Ingredient = apps.get_model('buddy_crocker', 'Ingredient')
Allergen = apps.get_model('buddy_crocker', 'Allergen')
Recipe = apps.get_model('buddy_crocker', 'Recipe')

User = get_user_model()


class IngredientSelectionForm(forms.Form):
    """Form for selecting pantry ingredients."""

    ingredients = forms.ModelMultipleChoiceField(
        queryset=None,  # Set dynamically in view for user's pantry ingredients
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Select ingredients to use:"
    )

    def __str__(self):
        """Return a string representation of the form."""
        return "IngredientSelectionForm"


class IngredientForm(forms.ModelForm):
    """Form for creating and editing ingredients."""

    allergens = forms.ModelMultipleChoiceField(
        queryset=Allergen.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select all allergens present in this ingredient"
    )
    brand = forms.CharField(
        required=False,
        initial='Generic',
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Jif, Skippy, Organic Valley, or leave as Generic'
            }
        ),
        help_text='Specify brand for branded products, or leave as "Generic" for whole foods'
    )

    class Meta:
        model = Ingredient
        fields = ['name', 'brand', 'calories', 'allergens']
        widgets = {
            'name': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Enter ingredient name'}
            ),
            'calories': forms.NumberInput(
                attrs={'class': 'form-control', 'placeholder': 'Enter calorie count'}
            ),
        }
        error_messages = {
            "name": {
                "required": _("Please enter an ingredient name."),
                "max_length": _("That name is too long."),
            },
        }

    def clean_name(self):
        """Strip and validate ingredient name."""
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
            if not name:
                raise forms.ValidationError("Name cannot be empty or whitespace.")
        return name

    def clean_brand(self):
        """Default brand to 'Generic' if empty."""
        brand = self.cleaned_data.get('brand', '').strip()
        return brand if brand else 'Generic'

    def clean_calories(self):
        """Ensure calories field is not empty."""
        calories = self.cleaned_data.get('calories')
        if calories is None:
            raise forms.ValidationError("Calories cannot be empty")
        return calories

    def __str__(self):
        """Return string representation."""
        return f"IngredientForm({self.instance})"


class AIRecipeForm(forms.ModelForm):
    """Form for AI-generated recipe editing, including ingredient selection."""

    ingredients = forms.ModelMultipleChoiceField(
        queryset=Ingredient.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Recipe
        fields = ['title', 'instructions', 'ingredients']
        widgets = {
            'title': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Enter recipe title'
                }
            ),
            'instructions': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 6,
                    'placeholder': 'Enter step-by-step instructions'
                }
            ),
        }
        error_messages = {
            "title": {
                "required": _("Please enter a title for your recipe."),
                "max_length": _("That title is a bit long—try shortening it."),
            },
            "instructions": {
                "required": _("Write cooking instructions."),
            },
        }

    def __str__(self):
        """Return string representation."""
        return f"AIRecipeForm({self.instance})"


class RecipeForm(forms.ModelForm):
    """Form for creating and editing recipes."""

    ingredients = forms.ModelMultipleChoiceField(
        queryset=Ingredient.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select ingredients used in this recipe"
    )

    class Meta:
        model = Recipe
        fields = ['title', 'instructions']
        widgets = {
            'title': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Enter recipe title'
                }
            ),
            'instructions': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 6,
                    'placeholder': 'Enter step-by-step instructions'
                }
            ),
        }
        error_messages = {
            "title": {
                "required": _("Please enter a title for your recipe."),
                "max_length": _("That title is a bit long."),
            },
            "instructions": {
                "required": _("Write a few steps so people can make it."),
            },
        }
        help_texts = {
            'title': 'Give your recipe a descriptive title',
            'instructions': 'Provide clear step-by-step instructions',
        }

    def clean_title(self):
        """Strip and validate recipe title."""
        title = self.cleaned_data.get('title')
        if title:
            title = title.strip()
            if not title:
                raise forms.ValidationError("Title cannot be empty or whitespace.")
        return title

    def clean_instructions(self):
        """Strip and validate recipe instructions."""
        instructions = self.cleaned_data.get('instructions')
        if instructions:
            instructions = instructions.strip()
            if not instructions:
                raise forms.ValidationError("Instructions cannot be empty or whitespace.")
        return instructions

    def __str__(self):
        """Return string representation."""
        return f"RecipeForm({self.instance})"


class UserForm(forms.ModelForm):
    """Form to edit user personal info."""

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username']

    def __str__(self):
        """Return string representation."""
        return "UserForm"


class ProfileForm(forms.ModelForm):
    """Form to edit user profile allergens."""

    allergens = forms.ModelMultipleChoiceField(
        queryset=Allergen.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Profile
        fields = ['allergens']

    def __str__(self):
        """Return string representation."""
        return "ProfileForm"


class CustomUserCreationForm(UserCreationForm):
    """Custom user creation form with allergen selection."""

    first_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    allergens = forms.ModelMultipleChoiceField(
        queryset=Allergen.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = [
            'username', 'first_name', 'last_name', 'email', 'password1', 'password2'
        ]

    def save(self, commit=True):
        """Save user and create/update profile with allergens."""
        user = super().save(commit=commit)
        if commit:
            profile, _created = Profile.objects.get_or_create(user=user)
            allergens = self.cleaned_data.get('allergens')
            if allergens:
                profile.allergens.set(allergens)
                profile.save()
        return user

    def __str__(self):
        """Return string representation."""
        return "CustomUserCreationForm"
     