"""
Unit tests for Buddy Crocker URL routing.

Tests URL patterns, reverse resolution, and URL parameter handling.
Updated to include USDA search endpoint.
"""
from django.test import TestCase
from django.urls import reverse, resolve
from buddy_crocker import views


class URLRoutingTest(TestCase):
    """Test cases for URL pattern configuration."""

    def test_index_url_resolves(self):
        """Test that the root URL resolves to the index view."""
        url = reverse('index')
        self.assertEqual(url, '/')
        self.assertEqual(resolve(url).func, views.index)

    def test_pantry_url_resolves(self):
        """Test that the pantry URL resolves to the pantry view."""
        url = reverse('pantry')
        self.assertEqual(url, '/pantry/')
        self.assertEqual(resolve(url).func, views.pantry)

    def test_recipe_search_url_resolves(self):
        """Test that the recipe search URL resolves to the recipe_search view."""
        url = reverse('recipe-search')
        self.assertEqual(url, '/recipe-search/')
        self.assertEqual(resolve(url).func, views.recipe_search)

    def test_add_recipe_url_resolves(self):
        """Test that the add recipe URL resolves to the add_recipe view."""
        url = reverse('add-recipe')
        self.assertEqual(url, '/add-recipe/')
        self.assertEqual(resolve(url).func, views.add_recipe)

    def test_add_ingredient_url_resolves(self):
        """Test that the add ingredient URL resolves to the add_ingredient view."""
        url = reverse('add-ingredient')
        self.assertEqual(url, '/add-ingredient/')
        self.assertEqual(resolve(url).func, views.add_ingredient)

    def test_recipe_detail_url_resolves(self):
        """Test that the recipe detail URL resolves with pk parameter."""
        url = reverse('recipe-detail', args=[1])
        self.assertEqual(url, '/recipe/1/')
        self.assertEqual(resolve(url).func, views.recipe_detail)

    def test_recipe_detail_url_with_different_pk(self):
        """Test that recipe detail URL works with various pk values."""
        for pk in [1, 42, 999]:
            url = reverse('recipe-detail', args=[pk])
            self.assertEqual(url, f'/recipe/{pk}/')
            resolved = resolve(url)
            self.assertEqual(resolved.func, views.recipe_detail)
            self.assertEqual(resolved.kwargs['pk'], pk)

    def test_ingredient_detail_url_resolves(self):
        """Test that the ingredient detail URL resolves with pk parameter."""
        url = reverse('ingredient-detail', args=[1])
        self.assertEqual(url, '/ingredient/1/')
        self.assertEqual(resolve(url).func, views.ingredient_detail)

    def test_ingredient_detail_url_with_different_pk(self):
        """Test that ingredient detail URL works with various pk values."""
        for pk in [5, 100, 777]:
            url = reverse('ingredient-detail', args=[pk])
            self.assertEqual(url, f'/ingredient/{pk}/')
            resolved = resolve(url)
            self.assertEqual(resolved.func, views.ingredient_detail)
            self.assertEqual(resolved.kwargs['pk'], pk)

    def test_allergen_detail_url_resolves(self):
        """Test that the allergen detail URL resolves with pk parameter."""
        url = reverse('allergen-detail', args=[1])
        self.assertEqual(url, '/allergen/1/')
        self.assertEqual(resolve(url).func, views.allergen_detail)

    def test_allergen_detail_url_with_different_pk(self):
        """Test that allergen detail URL works with various pk values."""
        for pk in [3, 25, 888]:
            url = reverse('allergen-detail', args=[pk])
            self.assertEqual(url, f'/allergen/{pk}/')
            resolved = resolve(url)
            self.assertEqual(resolved.func, views.allergen_detail)
            self.assertEqual(resolved.kwargs['pk'], pk)

    def test_profile_detail_url_resolves(self):
        """Test that the profile detail URL resolves with pk parameter."""
        url = reverse('profile-detail', args=[1])
        self.assertEqual(url, '/profile/1/')
        self.assertEqual(resolve(url).func, views.profile_detail)

    def test_profile_detail_url_with_different_pk(self):
        """Test that profile detail URL works with various pk values."""
        for pk in [10, 50, 123]:
            url = reverse('profile-detail', args=[pk])
            self.assertEqual(url, f'/profile/{pk}/')
            resolved = resolve(url)
            self.assertEqual(resolved.func, views.profile_detail)
            self.assertEqual(resolved.kwargs['pk'], pk)

    def test_usda_search_url_resolves(self):
        """Test that the USDA ingredient search API endpoint resolves."""
        url = reverse('search-usda-ingredients')
        self.assertEqual(url, '/api/search-ingredients/')
        self.assertEqual(resolve(url).func, views.search_usda_ingredients)


class URLNamingTest(TestCase):
    """Test cases for URL naming conventions."""

    def test_all_url_names_are_unique(self):
        """Test that all URL patterns have unique names."""
        url_names = [
            'index',
            'pantry',
            'recipe-search',
            'add-recipe',
            'add-ingredient',
            'recipe-detail',
            'ingredient-detail',
            'allergen-detail',
            'profile-detail',
            'search-usda-ingredients'
        ]
        
        # Each name should reverse to a unique URL
        urls = [reverse(name, args=[1] if 'detail' in name else []) for name in url_names]
        self.assertEqual(len(urls), len(set(urls)))

    def test_url_names_use_consistent_naming(self):
        """Test that URL names follow consistent kebab-case convention."""
        url_names = [
            'index',
            'pantry',
            'recipe-search',
            'add-recipe',
            'add-ingredient',
            'recipe-detail',
            'ingredient-detail',
            'allergen-detail',
            'profile-detail',
            'search-usda-ingredients'
        ]
        
        for name in url_names:
            # Should be lowercase and use hyphens
            self.assertEqual(name, name.lower())
            self.assertNotIn('_', name)


class URLParameterValidationTest(TestCase):
    """Test cases for URL parameter handling."""

    def test_recipe_detail_requires_pk_argument(self):
        """Test that recipe detail URL requires pk parameter."""
        with self.assertRaises(Exception):  # NoReverseMatch or TypeError
            reverse('recipe-detail')

    def test_ingredient_detail_requires_pk_argument(self):
        """Test that ingredient detail URL requires pk parameter."""
        with self.assertRaises(Exception):  # NoReverseMatch or TypeError
            reverse('ingredient-detail')

    def test_allergen_detail_requires_pk_argument(self):
        """Test that allergen detail URL requires pk parameter."""
        with self.assertRaises(Exception):  # NoReverseMatch or TypeError
            reverse('allergen-detail')

    def test_profile_detail_requires_pk_argument(self):
        """Test that profile detail URL requires pk parameter."""
        with self.assertRaises(Exception):  # NoReverseMatch or TypeError
            reverse('profile-detail')

    def test_urls_without_parameters_work_correctly(self):
        """Test that parameterless URLs work without arguments."""
        # These should work without arguments
        self.assertIsNotNone(reverse('index'))
        self.assertIsNotNone(reverse('pantry'))
        self.assertIsNotNone(reverse('recipe-search'))
        self.assertIsNotNone(reverse('add-recipe'))
        self.assertIsNotNone(reverse('add-ingredient'))
        self.assertIsNotNone(reverse('search-usda-ingredients'))

    def test_urls_without_parameters_reject_arguments(self):
        """Test that parameterless URLs don't accept extra arguments."""
        with self.assertRaises(Exception):  # NoReverseMatch
            reverse('index', args=[1])
        with self.assertRaises(Exception):  # NoReverseMatch
            reverse('pantry', args=[1])

    def test_detail_urls_accept_only_integer_pk(self):
        """Test that detail URLs work with integer pk values."""
        # These should work
        self.assertIsNotNone(reverse('recipe-detail', args=[1]))
        self.assertIsNotNone(reverse('recipe-detail', args=[999]))
        
        # String representations of integers should also work
        self.assertIsNotNone(reverse('recipe-detail', args=['123']))

    def test_detail_urls_with_zero_pk(self):
        """Test that detail URLs handle zero pk value."""
        url = reverse('recipe-detail', args=[0])
        self.assertEqual(url, '/recipe/0/')
        
        resolved = resolve(url)
        self.assertEqual(resolved.kwargs['pk'], 0)


class URLPatternStructureTest(TestCase):
    """Test cases for URL pattern structure and organization."""

    def test_all_urls_start_with_slash(self):
        """Test that all reversed URLs start with a forward slash."""
        url_configs = [
            ('index', []),
            ('pantry', []),
            ('recipe-search', []),
            ('add-recipe', []),
            ('add-ingredient', []),
            ('recipe-detail', [1]),
            ('ingredient-detail', [1]),
            ('allergen-detail', [1]),
            ('profile-detail', [1]),
            ('search-usda-ingredients', []),
        ]
        
        for name, args in url_configs:
            url = reverse(name, args=args)
            self.assertTrue(url.startswith('/'), 
                          f"URL '{name}' doesn't start with /: {url}")

    def test_all_urls_end_with_slash(self):
        """Test that all reversed URLs end with a forward slash (Django convention)."""
        url_configs = [
            ('index', []),
            ('pantry', []),
            ('recipe-search', []),
            ('add-recipe', []),
            ('add-ingredient', []),
            ('recipe-detail', [1]),
            ('ingredient-detail', [1]),
            ('allergen-detail', [1]),
            ('profile-detail', [1]),
            ('search-usda-ingredients', []),
        ]
        
        for name, args in url_configs:
            url = reverse(name, args=args)
            self.assertTrue(url.endswith('/'), 
                          f"URL '{name}' doesn't end with /: {url}")

    def test_detail_urls_follow_resource_pk_pattern(self):
        """Test that detail URLs follow the /resource/pk/ pattern."""
        detail_patterns = {
            'recipe-detail': 'recipe',
            'ingredient-detail': 'ingredient',
            'allergen-detail': 'allergen',
            'profile-detail': 'profile',
        }
        
        for url_name, resource in detail_patterns.items():
            url = reverse(url_name, args=[42])
            expected = f'/{resource}/42/'
            self.assertEqual(url, expected,
                           f"URL '{url_name}' doesn't match expected pattern: {expected}")

    def test_action_urls_follow_kebab_case(self):
        """Test that action URLs use kebab-case naming."""
        action_urls = [
            ('recipe-search', '/recipe-search/'),
            ('add-recipe', '/add-recipe/'),
            ('add-ingredient', '/add-ingredient/'),
        ]
        
        for name, expected_url in action_urls:
            url = reverse(name)
            self.assertEqual(url, expected_url)

    def test_api_urls_under_api_prefix(self):
        """Test that API endpoints are under /api/ prefix."""
        url = reverse('search-usda-ingredients')
        self.assertTrue(url.startswith('/api/'),
                       f"API URL doesn't start with /api/: {url}")


class URLReverseResolutionTest(TestCase):
    """Test cases for URL reverse resolution integrity."""

    def test_reverse_and_resolve_are_inverse_operations(self):
        """Test that reverse() and resolve() are inverse operations."""
        # Test URLs without parameters
        simple_urls = ['index', 'pantry', 'recipe-search', 'add-recipe', 
                      'add-ingredient', 'search-usda-ingredients']
        
        for url_name in simple_urls:
            reversed_url = reverse(url_name)
            resolved = resolve(reversed_url)
            self.assertEqual(resolved.url_name, url_name)

    def test_reverse_and_resolve_with_parameters(self):
        """Test that reverse() and resolve() work correctly with parameters."""
        detail_urls = [
            'recipe-detail',
            'ingredient-detail',
            'allergen-detail',
            'profile-detail'
        ]
        
        for url_name in detail_urls:
            pk_value = 15
            reversed_url = reverse(url_name, args=[pk_value])
            resolved = resolve(reversed_url)
            
            self.assertEqual(resolved.url_name, url_name)
            self.assertEqual(resolved.kwargs['pk'], pk_value)

    def test_multiple_reverse_calls_return_same_url(self):
        """Test that multiple reverse() calls return consistent results."""
        url1 = reverse('recipe-detail', args=[7])
        url2 = reverse('recipe-detail', args=[7])
        url3 = reverse('recipe-detail', args=[7])
        
        self.assertEqual(url1, url2)
        self.assertEqual(url2, url3)

    def test_resolve_returns_correct_view_function(self):
        """Test that resolve() returns the correct view function for each URL."""
        url_view_mapping = {
            '/': views.index,
            '/pantry/': views.pantry,
            '/recipe-search/': views.recipe_search,
            '/add-recipe/': views.add_recipe,
            '/add-ingredient/': views.add_ingredient,
            '/recipe/1/': views.recipe_detail,
            '/ingredient/1/': views.ingredient_detail,
            '/allergen/1/': views.allergen_detail,
            '/profile/1/': views.profile_detail,
            '/api/search-ingredients/': views.search_usda_ingredients,
        }
        
        for url, expected_view in url_view_mapping.items():
            resolved = resolve(url)
            self.assertEqual(resolved.func, expected_view,
                           f"URL {url} doesn't resolve to expected view")


class AdminURLTest(TestCase):
    """Test cases for Django admin URL configuration."""

    def test_admin_url_exists(self):
        """Test that the admin URL is configured."""
        url = reverse('admin:index')
        self.assertTrue(url.startswith('/admin/'))

    def test_admin_url_resolves(self):
        """Test that the admin URL resolves correctly."""
        resolved = resolve('/admin/')
        # Just verify it resolves without error
        self.assertIsNotNone(resolved)