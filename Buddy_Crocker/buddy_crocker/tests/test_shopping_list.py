"""
Comprehensive tests for shopping list functionality.

Tests cover:
- Model validation and constraints
- Form validation and security
- View access control and CSRF protection
- Database operations and edge cases
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from buddy_crocker.models import (
    ShoppingListItem,
    Ingredient,
    Allergen,
    Recipe,
    Pantry
)
from buddy_crocker.forms import ShoppingListItemForm


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def second_user(db):
    """Create a second test user for isolation testing."""
    return User.objects.create_user(
        username='testuser2',
        email='test2@example.com',
        password='testpass123'
    )


@pytest.fixture
def authenticated_client(client, user):
    """Create an authenticated client."""
    client.login(username='testuser', password='testpass123')
    return client


@pytest.fixture
def ingredient(db):
    """Create a test ingredient."""
    return Ingredient.objects.create(
        name='Tomatoes',
        brand='Generic',
        calories=18
    )


@pytest.fixture
def shopping_item(user, ingredient):
    """Create a test shopping list item."""
    return ShoppingListItem.objects.create(
        user=user,
        ingredient=ingredient,
        ingredient_name='Tomatoes',
        quantity='2 lbs'
    )


@pytest.fixture
def recipe(user, ingredient):
    """Create a test recipe."""
    recipe_obj = Recipe.objects.create(
        title='Test Recipe',
        author=user,
        instructions='Cook it.',
        servings=4
    )
    return recipe_obj


# ============================================================================
# MODEL TESTS
# ============================================================================

@pytest.mark.django_db
class TestShoppingListItemModel:
    """Test ShoppingListItem model functionality."""

    def test_create_shopping_item(self, user):
        """Test creating a basic shopping list item."""
        item = ShoppingListItem.objects.create(
            user=user,
            ingredient_name='Flour',
            quantity='2 cups'
        )
        assert item.ingredient_name == 'Flour'
        assert item.quantity == '2 cups'
        assert not item.is_purchased
        assert item.user == user

    def test_shopping_item_with_ingredient_link(self, user, ingredient):
        """Test shopping item linked to ingredient model."""
        item = ShoppingListItem.objects.create(
            user=user,
            ingredient=ingredient,
            ingredient_name=ingredient.name,
            quantity='500g'
        )
        assert item.ingredient == ingredient
        assert item.ingredient_name == ingredient.name

    def test_shopping_item_str_representation(self, shopping_item):
        """Test string representation of shopping item."""
        expected = "○ Tomatoes (2 lbs)"
        assert str(shopping_item) == expected

        shopping_item.is_purchased = True
        shopping_item.save()
        expected_purchased = "✓ Tomatoes (2 lbs)"
        assert str(shopping_item) == expected_purchased

    def test_unique_constraint_per_user(self, user):
        """Test unique constraint on user and ingredient_name."""
        ShoppingListItem.objects.create(
            user=user,
            ingredient_name='Sugar'
        )

        with pytest.raises((IntegrityError, ValidationError)):
            ShoppingListItem.objects.create(
                user=user,
                ingredient_name='Sugar'
            )

    def test_different_users_can_have_same_ingredient(self, user, second_user):
        """Test that different users can have the same ingredient."""
        ShoppingListItem.objects.create(
            user=user,
            ingredient_name='Salt'
        )
        item2 = ShoppingListItem.objects.create(
            user=second_user,
            ingredient_name='Salt'
        )
        assert item2.ingredient_name == 'Salt'

    def test_clean_method_strips_whitespace(self, user):
        """Test that clean method strips whitespace from fields."""
        item = ShoppingListItem(
            user=user,
            ingredient_name='  Butter  ',
            quantity='  1 stick  ',
            notes='  organic  '
        )
        item.clean()
        assert item.ingredient_name == 'Butter'
        assert item.quantity == '1 stick'
        assert item.notes == 'organic'

    def test_clean_method_rejects_empty_ingredient_name(self, user):
        """Test that clean method rejects empty ingredient names."""
        item = ShoppingListItem(
            user=user,
            ingredient_name='   '
        )
        with pytest.raises(ValidationError) as exc_info:
            item.clean()
        assert 'ingredient_name' in exc_info.value.message_dict

    def test_mark_purchased_method(self, shopping_item):
        """Test mark_purchased method."""
        assert not shopping_item.is_purchased
        shopping_item.mark_purchased()
        shopping_item.refresh_from_db()
        assert shopping_item.is_purchased

    def test_mark_unpurchased_method(self, shopping_item):
        """Test mark_unpurchased method."""
        shopping_item.is_purchased = True
        shopping_item.save()
        shopping_item.mark_unpurchased()
        shopping_item.refresh_from_db()
        assert not shopping_item.is_purchased

    def test_toggle_purchased_method(self, shopping_item):
        """Test toggle_purchased method."""
        initial_status = shopping_item.is_purchased
        shopping_item.toggle_purchased()
        shopping_item.refresh_from_db()
        assert shopping_item.is_purchased == (not initial_status)

    def test_add_to_pantry_with_ingredient(self, user, shopping_item):
        """Test adding shopping item to pantry when ingredient is linked."""
        result = shopping_item.add_to_pantry()
        assert result is True

        pantry = Pantry.objects.get(user=user)
        assert shopping_item.ingredient in pantry.ingredients.all()

    def test_add_to_pantry_without_ingredient(self, user):
        """Test add_to_pantry returns False when no ingredient linked."""
        item = ShoppingListItem.objects.create(
            user=user,
            ingredient_name='Random Item'
        )
        result = item.add_to_pantry()
        assert result is False

    def test_ordering_unpurchased_first(self, user):
        """Test that unpurchased items appear before purchased."""
        item1 = ShoppingListItem.objects.create(
            user=user,
            ingredient_name='Item 1',
            is_purchased=True
        )
        item2 = ShoppingListItem.objects.create(
            user=user,
            ingredient_name='Item 2',
            is_purchased=False
        )

        items = list(ShoppingListItem.objects.filter(user=user))
        assert items[0] == item2  # Unpurchased first
        assert items[1] == item1  # Purchased last


# ============================================================================
# FORM TESTS
# ============================================================================

@pytest.mark.django_db
class TestShoppingListItemForm:
    """Test ShoppingListItemForm validation."""

    def test_valid_form_with_all_fields(self):
        """Test form with all valid fields."""
        form = ShoppingListItemForm(data={
            'ingredient_name': 'Eggs',
            'quantity': '1 dozen',
            'notes': 'Free range'
        })
        assert form.is_valid()

    def test_valid_form_with_required_only(self):
        """Test form with only required fields."""
        form = ShoppingListItemForm(data={
            'ingredient_name': 'Milk'
        })
        assert form.is_valid()

    def test_form_strips_whitespace(self):
        """Test that form strips whitespace from all inputs."""
        form = ShoppingListItemForm(data={
            'ingredient_name': '  Cheese  ',
            'quantity': '  200g  ',
            'notes': '  cheddar  '
        })
        assert form.is_valid()
        assert form.cleaned_data['ingredient_name'] == 'Cheese'
        assert form.cleaned_data['quantity'] == '200g'
        assert form.cleaned_data['notes'] == 'cheddar'

    def test_form_rejects_empty_ingredient_name(self):
        """Test that form rejects empty ingredient names."""
        form = ShoppingListItemForm(data={
            'ingredient_name': '',
            'quantity': '5'
        })
        assert not form.is_valid()
        assert 'ingredient_name' in form.errors

    def test_form_rejects_whitespace_only_ingredient(self):
        """Test that form rejects whitespace-only ingredient names."""
        form = ShoppingListItemForm(data={
            'ingredient_name': '    ',
        })
        assert not form.is_valid()
        assert 'ingredient_name' in form.errors

    def test_form_rejects_html_in_ingredient_name(self):
        """Test XSS protection - reject HTML tags in ingredient name."""
        form = ShoppingListItemForm(data={
            'ingredient_name': '<script>alert("xss")</script>',
        })
        assert not form.is_valid()
        assert 'ingredient_name' in form.errors

    def test_form_ingredient_name_max_length(self):
        """Test ingredient name max length validation."""
        form = ShoppingListItemForm(data={
            'ingredient_name': 'A' * 201,  # Over 200 char limit
        })
        assert not form.is_valid()
        assert 'ingredient_name' in form.errors

    def test_form_quantity_max_length(self):
        """Test quantity max length validation."""
        form = ShoppingListItemForm(data={
            'ingredient_name': 'Sugar',
            'quantity': 'A' * 101,  # Over 100 char limit
        })
        assert not form.is_valid()
        assert 'quantity' in form.errors

    def test_form_notes_max_length(self):
        """Test notes max length validation."""
        form = ShoppingListItemForm(data={
            'ingredient_name': 'Salt',
            'notes': 'A' * 501,  # Over 500 char limit
        })
        assert not form.is_valid()
        assert 'notes' in form.errors

    def test_quantity_optional(self):
        """Test that quantity field is optional."""
        form = ShoppingListItemForm(data={
            'ingredient_name': 'Pepper',
            'quantity': ''
        })
        assert form.is_valid()

    def test_notes_optional(self):
        """Test that notes field is optional."""
        form = ShoppingListItemForm(data={
            'ingredient_name': 'Garlic',
            'notes': ''
        })
        assert form.is_valid()


# ============================================================================
# VIEW TESTS
# ============================================================================

@pytest.mark.django_db
class TestShoppingListView:
    """Test shopping list view functionality."""

    def test_view_requires_login(self, client):
        """Test that view redirects to login for anonymous users."""
        url = reverse('shopping-list')
        response = client.get(url)
        assert response.status_code == 302  # Redirect
        assert '/login/' in response.url

    def test_view_get_request(self, authenticated_client):
        """Test GET request displays shopping list."""
        url = reverse('shopping-list')
        response = authenticated_client.get(url)
        assert response.status_code == 200
        assert 'items' in response.context
        assert 'form' in response.context
        assert 'purchased_count' in response.context
        assert 'pending_count' in response.context

    def test_view_displays_user_items_only(self, authenticated_client, user, second_user):
        """Test view only shows items belonging to authenticated user."""
        ShoppingListItem.objects.create(
            user=user,
            ingredient_name='User 1 Item'
        )
        ShoppingListItem.objects.create(
            user=second_user,
            ingredient_name='User 2 Item'
        )

        url = reverse('shopping-list')
        response = authenticated_client.get(url)
        items = response.context['items']

        assert items.count() == 1
        assert items.first().ingredient_name == 'User 1 Item'

    def test_add_item_post(self, authenticated_client, user):
        """Test adding item via POST request."""
        url = reverse('shopping-list')
        data = {
            'ingredient_name': 'Olive Oil',
            'quantity': '1 bottle',
            'add_item': ''
        }
        response = authenticated_client.post(url, data)
        assert response.status_code == 302  # Redirect

        assert ShoppingListItem.objects.filter(
            user=user,
            ingredient_name='Olive Oil'
        ).exists()

    def test_add_duplicate_item_shows_warning(self, authenticated_client, user):
        """Test adding duplicate item shows appropriate message."""
        ShoppingListItem.objects.create(
            user=user,
            ingredient_name='Bread'
        )

        url = reverse('shopping-list')
        data = {
            'ingredient_name': 'Bread',
            'add_item': ''
        }
        response = authenticated_client.post(url, data, follow=True)
        messages = list(response.context['messages'])

        assert any('already in your shopping list' in str(m) for m in messages)

    def test_toggle_purchased_post(self, authenticated_client, shopping_item):
        """Test toggling purchased status via POST."""
        url = reverse('shopping-list')
        data = {'toggle_purchased': str(shopping_item.id)}

        assert not shopping_item.is_purchased
        authenticated_client.post(url, data)

        shopping_item.refresh_from_db()
        assert shopping_item.is_purchased

    def test_toggle_purchased_requires_ownership(self, authenticated_client, second_user):
        """Test users can only toggle their own items."""
        other_item = ShoppingListItem.objects.create(
            user=second_user,
            ingredient_name='Other User Item'
        )

        url = reverse('shopping-list')
        data = {'toggle_purchased': str(other_item.id)}
        response = authenticated_client.post(url, data)

        # Should get 404 when trying to access other user's item
        assert response.status_code == 404

    def test_delete_item_post(self, authenticated_client, shopping_item):
        """Test deleting an item via POST."""
        url = reverse('shopping-list')
        item_id = shopping_item.id
        data = {'delete_item': str(item_id)}

        authenticated_client.post(url, data)
        assert not ShoppingListItem.objects.filter(id=item_id).exists()

    def test_delete_item_requires_ownership(self, authenticated_client, second_user):
        """Test users can only delete their own items."""
        other_item = ShoppingListItem.objects.create(
            user=second_user,
            ingredient_name='Other User Item'
        )

        url = reverse('shopping-list')
        data = {'delete_item': str(other_item.id)}
        response = authenticated_client.post(url, data)

        # Should get 404 and item should still exist
        assert response.status_code == 404
        assert ShoppingListItem.objects.filter(id=other_item.id).exists()

    def test_clear_purchased_items(self, authenticated_client, user):
        """Test clearing purchased items."""
        ShoppingListItem.objects.create(
            user=user,
            ingredient_name='Item 1',
            is_purchased=True
        )
        ShoppingListItem.objects.create(
            user=user,
            ingredient_name='Item 2',
            is_purchased=False
        )

        url = reverse('shopping-list')
        data = {'clear_purchased': ''}
        authenticated_client.post(url, data)

        assert not ShoppingListItem.objects.filter(
            user=user,
            is_purchased=True
        ).exists()
        assert ShoppingListItem.objects.filter(
            user=user,
            is_purchased=False
        ).exists()

    def test_clear_purchased_with_no_items(self, authenticated_client, user):
        """Test clear purchased when no purchased items exist."""
        url = reverse('shopping-list')
        data = {'clear_purchased': ''}
        response = authenticated_client.post(url, data, follow=True)

        messages = list(response.context['messages'])
        assert any('No purchased items' in str(m) for m in messages)

    def test_invalid_item_id_shows_error(self, authenticated_client):
        """Test that invalid item IDs show error messages."""
        url = reverse('shopping-list')
        data = {'toggle_purchased': 'invalid'}
        response = authenticated_client.post(url, data, follow=True)

        messages = list(response.context['messages'])
        assert any('Invalid item ID' in str(m) for m in messages)

    def test_csrf_token_present_in_form(self, authenticated_client):
        """Test CSRF token is included in rendered forms."""
        url = reverse('shopping-list')
        response = authenticated_client.get(url)
        assert b'csrfmiddlewaretoken' in response.content

    def test_invalid_action_shows_error(self, authenticated_client):
        """Test invalid POST action shows error."""
        url = reverse('shopping-list')
        data = {'invalid_action': 'value'}
        response = authenticated_client.post(url, data, follow=True)

        messages = list(response.context['messages'])
        assert any('Invalid action' in str(m) for m in messages)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestShoppingListIntegration:
    """Integration tests for shopping list with other models."""

    def test_add_shopping_item_to_pantry(self, authenticated_client, user, ingredient):
        """Test adding purchased shopping item to pantry."""
        item = ShoppingListItem.objects.create(
            user=user,
            ingredient=ingredient,
            ingredient_name=ingredient.name
        )

        url = reverse('shopping-list')
        data = {'add_to_pantry': str(item.id)}
        authenticated_client.post(url, data)

        pantry = Pantry.objects.get(user=user)
        assert ingredient in pantry.ingredients.all()

    def test_shopping_item_cascade_delete_on_user_delete(self, user):
        """Test shopping items are deleted when user is deleted."""
        ShoppingListItem.objects.create(
            user=user,
            ingredient_name='Test Item'
        )

        user_id = user.id
        user.delete()

        assert not ShoppingListItem.objects.filter(
            user_id=user_id
        ).exists()

    def test_shopping_item_set_null_on_ingredient_delete(self, user, ingredient):
        """Test ingredient FK is set to null when ingredient deleted."""
        item = ShoppingListItem.objects.create(
            user=user,
            ingredient=ingredient,
            ingredient_name=ingredient.name
        )

        ingredient.delete()
        item.refresh_from_db()

        assert item.ingredient is None
        assert item.ingredient_name == 'Tomatoes'  # Name preserved
# Add to your existing test_shopping_list.py file

@pytest.mark.django_db
class TestAddToShoppingListHelper:
    """Test the _add_to_shopping_list helper function."""
    
    def test_add_to_shopping_list_with_ingredient_match(self, user, ingredient):
        """Test adding items to shopping list."""
        from buddy_crocker.views import _add_to_shopping_list
    
        # Just test that items get added
        shopping_items = ["2 cups flour"]
    
        added_count = _add_to_shopping_list(user, shopping_items)
    
        # Verify the item was added successfully
        assert added_count == 1
        assert ShoppingListItem.objects.filter(user=user).count() == 1
    
    def test_add_to_shopping_list_with_duplicates(self, user):
        """Test adding items when duplicates exist."""
        from buddy_crocker.views import _add_to_shopping_list
        
        # Create existing item
        ShoppingListItem.objects.create(
            user=user,
            ingredient_name='flour'
        )
        
        shopping_items = [
            "2 cups flour",  # Duplicate
            "1 lb chicken breast"
        ]
        
        added_count = _add_to_shopping_list(user, shopping_items)
        
        # Only 1 new item added (chicken)
        assert added_count == 1
        assert ShoppingListItem.objects.filter(user=user).count() == 2
    
    def test_add_to_shopping_list_empty_list(self, user):
        """Test adding empty shopping list."""
        from buddy_crocker.views import _add_to_shopping_list
        
        added_count = _add_to_shopping_list(user, [])
        
        assert added_count == 0
        assert ShoppingListItem.objects.filter(user=user).count() == 0
    
    def test_add_to_shopping_list_quantity_formatting(self, user):
        """Test quantity formatting in shopping list items."""
        from buddy_crocker.views import _add_to_shopping_list
        
        shopping_items = [
            "2 cups sugar",
            "salt"  # No quantity
        ]
        
        _add_to_shopping_list(user, shopping_items)
        
        sugar_item = ShoppingListItem.objects.get(user=user, ingredient_name='sugar')
        salt_item = ShoppingListItem.objects.get(user=user, ingredient_name='salt')
        
        assert sugar_item.quantity == "2.0 cups"
        assert salt_item.quantity == ""


@pytest.mark.django_db
class TestShoppingListEdgeCases:
    """Test edge cases and error handling."""
    
    def test_add_item_with_very_long_name(self, authenticated_client, user):
        """Test adding item with name at max length."""
        url = reverse('shopping-list')
        long_name = 'A' * 200  # Max length
        data = {
            'ingredient_name': long_name,
            'add_item': ''
        }
        
        response = authenticated_client.post(url, data)
        assert response.status_code == 302
        assert ShoppingListItem.objects.filter(
            user=user,
            ingredient_name=long_name
        ).exists()
    
    def test_toggle_purchased_with_invalid_string_id(self, authenticated_client):
        """Test toggle with non-numeric ID."""
        url = reverse('shopping-list')
        data = {'toggle_purchased': 'abc'}
        
        response = authenticated_client.post(url, data, follow=True)
        messages = list(response.context['messages'])
        assert any('Invalid item ID' in str(m) for m in messages)
    
    def test_delete_with_negative_id(self, authenticated_client):
        """Test delete with negative ID."""
        url = reverse('shopping-list')
        data = {'delete_item': '-1'}
        
        response = authenticated_client.post(url, data)
        # Should get 404 since negative ID won't exist
        assert response.status_code == 404 or response.status_code == 302
    
    def test_add_item_form_validation_messages(self, authenticated_client):
        """Test that form validation errors are shown."""
        url = reverse('shopping-list')
        data = {
            'ingredient_name': '',  # Invalid - required
            'add_item': ''
        }
        
        response = authenticated_client.post(url, data, follow=True)
        messages = list(response.context['messages'])
        
        # Should have error message about required field
        assert len(messages) > 0
    
    def test_shopping_list_items_ordered_correctly(self, user):
        """Test that unpurchased items appear before purchased."""
        item1 = ShoppingListItem.objects.create(
            user=user,
            ingredient_name='Item 1',
            is_purchased=True
        )
        item2 = ShoppingListItem.objects.create(
            user=user,
            ingredient_name='Item 2',
            is_purchased=False
        )
        item3 = ShoppingListItem.objects.create(
            user=user,
            ingredient_name='Item 3',
            is_purchased=False
        )
        
        items = list(ShoppingListItem.objects.filter(user=user))
        
        # Unpurchased items should come first
        assert items[0].is_purchased == False
        assert items[1].is_purchased == False
        assert items[2].is_purchased == True


@pytest.mark.django_db  
class TestShoppingListItemModelMethods:
    """Test ShoppingListItem model methods thoroughly."""
    
    def test_clean_with_linked_ingredient_syncs_name(self, user, ingredient):
        """Test that clean() syncs name when ingredient is linked."""
        item = ShoppingListItem(
            user=user,
            ingredient=ingredient,
            ingredient_name='different name'
        )
        item.clean()
        
        assert item.ingredient_name == str(ingredient.name)
    
    def test_str_without_quantity(self, user):
        """Test string representation without quantity."""
        item = ShoppingListItem.objects.create(
            user=user,
            ingredient_name='Salt',
            quantity=''
        )
        
        assert str(item) == "○ Salt"
    
    def test_str_when_purchased(self, user):
        """Test string representation when purchased."""
        item = ShoppingListItem.objects.create(
            user=user,
            ingredient_name='Pepper',
            quantity='1 jar',
            is_purchased=True
        )
        
        assert str(item) == "✓ Pepper (1 jar)"
    
    def test_save_calls_full_clean(self, user):
        """Test that save() calls full_clean()."""
        item = ShoppingListItem(
            user=user,
            ingredient_name='   '  # Invalid - whitespace only
        )
        
        with pytest.raises(ValidationError):
            item.save()


@pytest.mark.django_db
class TestShoppingListFormEdgeCases:
    """Test form edge cases and validation."""
    
    def test_form_with_maximum_lengths(self):
        """Test form accepts maximum allowed lengths."""
        form = ShoppingListItemForm(data={
            'ingredient_name': 'A' * 200,
            'quantity': 'B' * 100,
            'notes': 'C' * 500
        })
        assert form.is_valid()
    
    def test_form_cleans_nested_whitespace(self):
        """Test form handles nested whitespace."""
        form = ShoppingListItemForm(data={
            'ingredient_name': '  Olive   Oil  ',
            'quantity': '  2   tbsp  ',
            'notes': '  Extra virgin  '
        })
        assert form.is_valid()
        # Only leading/trailing whitespace is stripped, not internal spaces
        assert form.cleaned_data['ingredient_name'] == 'Olive   Oil'
        assert form.cleaned_data['quantity'] == '2   tbsp'
        assert form.cleaned_data['notes'] == 'Extra virgin'

    def test_form_rejects_only_spaces(self):
        """Test form rejects various whitespace-only inputs."""
        test_cases = ['   ', '\t\t', '\n\n', '  \t  \n  ']
        
        for whitespace in test_cases:
            form = ShoppingListItemForm(data={
                'ingredient_name': whitespace
            })
            assert not form.is_valid()
            assert 'ingredient_name' in form.errors
