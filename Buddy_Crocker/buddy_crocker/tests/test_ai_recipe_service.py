"""
Comprehensive tests for AI Recipe Service.
"""

import json
from unittest import TestCase, mock
from unittest.mock import patch, MagicMock
from buddy_crocker.ai_recipe_service import generate_ai_recipes, _extract_recipes


# ============================================================================
# GENERATE AI RECIPES TESTS
# ============================================================================


class TestGenerateAIRecipes(TestCase):
    """Test generate_ai_recipes function."""
    
    @patch('buddy_crocker.ai_recipe_service.settings.OPENAI_API_KEY', None)
    def test_no_api_key_raises_error(self):
        """Test that missing API key raises RuntimeError."""
        with self.assertRaises(RuntimeError) as exc_info:
            generate_ai_recipes(['flour', 'eggs'])
        
        self.assertIn("OPENAI_API_KEY is not configured", str(exc_info.exception))
    
    @patch('buddy_crocker.ai_recipe_service.OpenAI')
    @patch('buddy_crocker.ai_recipe_service.settings.OPENAI_API_KEY', 'test-key')
    def test_successful_recipe_generation(self, mock_openai):
        """Test successful API call returns recipes."""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "recipes": [
                {
                    "title": "Pancakes",
                    "ingredients": ["2 cups flour", "3 eggs", "1 cup milk"],
                    "instructions": "1. Mix ingredients\n2. Cook on griddle",
                    "uses_only_pantry": True
                },
                {
                    "title": "Scrambled Eggs",
                    "ingredients": ["4 eggs", "2 tbsp butter"],
                    "instructions": "1. Beat eggs\n2. Cook in pan",
                    "uses_only_pantry": True
                },
                {
                    "title": "French Toast",
                    "ingredients": ["4 eggs", "1 cup milk", "8 slices bread"],
                    "instructions": "1. Mix eggs and milk\n2. Dip bread\n3. Cook",
                    "uses_only_pantry": False
                },
                {
                    "title": "Omelette",
                    "ingredients": ["3 eggs", "1/4 cup cheese"],
                    "instructions": "1. Beat eggs\n2. Add cheese\n3. Fold",
                    "uses_only_pantry": False
                }
            ]
        })
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        recipes = generate_ai_recipes(['flour', 'eggs', 'milk'])
        
        self.assertEqual(len(recipes), 4)
        self.assertEqual(recipes[0]['title'], "Pancakes")
        self.assertTrue(recipes[0]['uses_only_pantry'])
        self.assertEqual(len(recipes[0]['ingredients']), 3)
        mock_openai.assert_called_once_with(api_key='test-key')
    
    @patch('buddy_crocker.ai_recipe_service.OpenAI')
    @patch('buddy_crocker.ai_recipe_service.settings.OPENAI_API_KEY', 'test-key')
    def test_api_error_raises_runtime_error(self, mock_openai):
        """Test that API errors are caught and wrapped."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_openai.return_value = mock_client
        
        with self.assertRaises(RuntimeError) as exc_info:
            generate_ai_recipes(['flour'])
        
        self.assertIn("Failed to generate recipes", str(exc_info.exception))
    
    @patch('buddy_crocker.ai_recipe_service.OpenAI')
    @patch('buddy_crocker.ai_recipe_service.settings.OPENAI_API_KEY', 'test-key')
    def test_empty_response_raises_error(self, mock_openai):
        """Test that empty API response raises error."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        with self.assertRaises(RuntimeError) as exc_info:
            generate_ai_recipes(['flour'])
        
        self.assertIn("empty response", str(exc_info.exception))
    
    @patch('buddy_crocker.ai_recipe_service.OpenAI')
    @patch('buddy_crocker.ai_recipe_service.settings.OPENAI_API_KEY', 'test-key')
    def test_invalid_json_raises_error(self, mock_openai):
        """Test that invalid JSON raises error."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "This is not JSON"
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        with self.assertRaises(RuntimeError) as exc_info:
            generate_ai_recipes(['flour'])
        
        self.assertIn("Failed to parse", str(exc_info.exception))
    
    @patch('buddy_crocker.ai_recipe_service.OpenAI')
    @patch('buddy_crocker.ai_recipe_service.settings.OPENAI_API_KEY', 'test-key')
    def test_fallback_json_extraction(self, mock_openai):
        """Test fallback extraction when JSON is embedded in text."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        # Response with JSON array embedded in text
        mock_response.choices[0].message.content = """
        Here are your recipes: [
            {
                "title": "Test Recipe",
                "ingredients": ["flour", "eggs"],
                "instructions": "Mix and cook",
                "uses_only_pantry": true
            }
        ]
        """
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        recipes = generate_ai_recipes(['flour', 'eggs'])
        
        self.assertGreaterEqual(len(recipes), 1)
        self.assertEqual(recipes[0]['title'], "Test Recipe")
    
    @patch('buddy_crocker.ai_recipe_service.OpenAI')
    @patch('buddy_crocker.ai_recipe_service.settings.OPENAI_API_KEY', 'test-key')
    def test_fewer_than_4_recipes(self, mock_openai):
        """Test handling when API returns fewer than 4 recipes."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "recipes": [
                {
                    "title": "Recipe 1",
                    "ingredients": ["flour"],
                    "instructions": "Cook it",
                    "uses_only_pantry": True
                },
                {
                    "title": "Recipe 2",
                    "ingredients": ["eggs"],
                    "instructions": "Cook it",
                    "uses_only_pantry": True
                }
            ]
        })
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        recipes = generate_ai_recipes(['flour', 'eggs'])
        
        # Should return what it got (2 recipes)
        self.assertEqual(len(recipes), 2)
    
    @patch('buddy_crocker.ai_recipe_service.OpenAI')
    @patch('buddy_crocker.ai_recipe_service.settings.OPENAI_API_KEY', 'test-key')
    def test_more_than_4_recipes_returns_first_4(self, mock_openai):
        """Test that more than 4 recipes are truncated to 4."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "recipes": [
                {
                    "title": f"Recipe {i}",
                    "ingredients": ["flour"],
                    "instructions": "Cook it",
                    "uses_only_pantry": True
                }
                for i in range(6)  # 6 recipes
            ]
        })
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        recipes = generate_ai_recipes(['flour'])
        
        # Should only return first 4
        self.assertEqual(len(recipes), 4)

    @patch('buddy_crocker.ai_recipe_service.OpenAI')
    @patch('buddy_crocker.ai_recipe_service.settings.OPENAI_API_KEY', 'test-key')
    @patch('buddy_crocker.ai_recipe_service.logger.warning')
    def test_padding_warning_logged(self, mock_warning, mock_openai):
        """Test logger.warning when <4 recipes returned."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "recipes": [{"title": "One", "ingredients": ["flour"], "instructions": "cook"}]
        })
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        recipes = generate_ai_recipes(['flour'])
        self.assertEqual(len(recipes), 1)
        mock_warning.assert_called_once()


# ============================================================================
# EXTRACT RECIPES TESTS
# ============================================================================


class TestExtractRecipes(TestCase):
    """Test _extract_recipes helper function."""
    
    def test_extract_from_dict_with_recipes_key(self):
        """Test extracting recipes from dict with 'recipes' key."""
        data = {
            "recipes": [
                {
                    "title": "Test Recipe",
                    "ingredients": ["flour", "eggs"],
                    "instructions": "Mix and cook",
                    "uses_only_pantry": True
                }
            ]
        }
        
        recipes = _extract_recipes(data)
        
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0]['title'], "Test Recipe")
        self.assertEqual(len(recipes[0]['ingredients']), 2)
    
    def test_extract_from_list(self):
        """Test extracting recipes from a list."""
        data = [
            {
                "title": "Recipe 1",
                "ingredients": ["flour"],
                "instructions": "Cook",
                "uses_only_pantry": False
            },
            {
                "title": "Recipe 2",
                "ingredients": ["eggs"],
                "instructions": "Fry",
                "uses_only_pantry": True
            }
        ]
        
        recipes = _extract_recipes(data)
        
        self.assertEqual(len(recipes), 2)
        self.assertEqual(recipes[0]['title'], "Recipe 1")
        self.assertTrue(recipes[1]['uses_only_pantry'])
    
    def test_skip_invalid_items(self):
        """Test that invalid items are skipped."""
        data = {
            "recipes": [
                {
                    "title": "Valid Recipe",
                    "ingredients": ["flour"],
                    "instructions": "Cook",
                    "uses_only_pantry": True
                },
                {
                    "title": "",  # Invalid - empty title
                    "ingredients": ["eggs"],
                    "instructions": "Cook"
                },
                {
                    "title": "No Ingredients",
                    "ingredients": [],  # Invalid - no ingredients
                    "instructions": "Cook"
                },
                {
                    "title": "No Instructions",
                    "ingredients": ["milk"],
                    "instructions": ""  # Invalid - empty instructions
                },
                "not a dict"  # Invalid - not a dict
            ]
        }
        
        recipes = _extract_recipes(data)
        
        # Only the valid recipe should be extracted
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0]['title'], "Valid Recipe")
    
    def test_clean_whitespace_in_ingredients(self):
        """Test that whitespace is stripped from ingredients."""
        data = {
            "recipes": [
                {
                    "title": "Test",
                    "ingredients": ["  flour  ", "  eggs  ", ""],
                    "instructions": "Cook",
                    "uses_only_pantry": True
                }
            ]
        }
        
        recipes = _extract_recipes(data)
        
        # Empty ingredient should be filtered out
        self.assertEqual(len(recipes[0]['ingredients']), 2)
        self.assertEqual(recipes[0]['ingredients'][0], "flour")
        self.assertEqual(recipes[0]['ingredients'][1], "eggs")
    
    def test_uses_only_pantry_defaults_to_false(self):
        """Test that uses_only_pantry defaults to False if missing."""
        data = {
            "recipes": [
                {
                    "title": "Test",
                    "ingredients": ["flour"],
                    "instructions": "Cook"
                    # uses_only_pantry not specified
                }
            ]
        }
        
        recipes = _extract_recipes(data)
        
        self.assertFalse(recipes[0]['uses_only_pantry'])
    
    def test_unexpected_data_type_returns_empty_list(self):
        """Test that unexpected data types return empty list."""
        recipes = _extract_recipes("not a dict or list")
        self.assertEqual(recipes, [])
        
        recipes = _extract_recipes(12345)
        self.assertEqual(recipes, [])
        
        recipes = _extract_recipes(None)
        self.assertEqual(recipes, [])
    
    def test_empty_dict_returns_empty_list(self):
        """Test that empty dict returns empty list."""
        recipes = _extract_recipes({})
        self.assertEqual(recipes, [])
    
    def test_empty_list_returns_empty_list(self):
        """Test that empty list returns empty list."""
        recipes = _extract_recipes([])
        self.assertEqual(recipes, [])
    
    def test_type_coercion(self):
        """Test that fields are properly type-coerced."""
        data = {
            "recipes": [
                {
                    "title": 123,  # Will be converted to string
                    "ingredients": ["flour"],
                    "instructions": 456,  # Will be converted to string
                    "uses_only_pantry": "yes"  # Will be converted to bool (truthy)
                }
            ]
        }
        
        recipes = _extract_recipes(data)
        
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0]['title'], "123")
        self.assertEqual(recipes[0]['instructions'], "456")
        self.assertTrue(recipes[0]['uses_only_pantry'])

    @patch('buddy_crocker.ai_recipe_service.logger.warning')
    def test_extract_unexpected_type_warning(self, mock_warning):
        """Test logger.warning for unexpected data type."""
        from buddy_crocker.ai_recipe_service import _extract_recipes
        result = _extract_recipes(12345)
        self.assertEqual(result, [])
        mock_warning.assert_called_once()  

    @patch('buddy_crocker.ai_recipe_service.OpenAI')
    @patch('buddy_crocker.ai_recipe_service.settings.OPENAI_API_KEY', 'test-key')
    @patch('buddy_crocker.ai_recipe_service.logger')
    def test_fewer_than_4_recipes_logs_warning(self, mock_logger, mock_openai):
        """When fewer than 4 recipes are returned, a warning is logged."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "recipes": [
                {
                    "title": "Only One",
                    "ingredients": ["flour"],
                    "instructions": "Cook it",
                    "uses_only_pantry": True,
                }
            ]
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        recipes = generate_ai_recipes(['flour'])

        self.assertEqual(len(recipes), 1)
        mock_logger.warning.assert_called()  # covers the padding warning line

    @patch('buddy_crocker.ai_recipe_service.logger')
    def test_unexpected_type_logs_warning(self, mock_logger):
        """Unexpected data types should log a warning and return []."""
        from buddy_crocker.ai_recipe_service import _extract_recipes

        result = _extract_recipes(12345)  # not dict or list
        self.assertEqual(result, [])
        mock_logger.warning.assert_called()  # hits the "Unexpected data type" line
