"""Tests for AI recipe generation service."""
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from buddy_crocker.ai_recipe_service import generate_ai_recipes


class AIRecipeServiceTest(TestCase):
    """Test AI recipe generation."""
    
    @override_settings(OPENAI_API_KEY='test-api-key')
    @patch('buddy_crocker.ai_recipe_service.OpenAI')
    def test_generate_ai_recipes_success(self, mock_openai_class):
        """Test successful recipe generation."""
        # Mock the OpenAI client and response
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(
            message=MagicMock(
                content='[{"title": "Test Recipe", "ingredients": ["1 cup rice"], "instructions": "Cook rice"}]'
            )
        )]
        mock_client.chat.completions.create.return_value = mock_response
        
        recipes = generate_ai_recipes(['rice'])
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0]['title'], 'Test Recipe')
    
    @override_settings(OPENAI_API_KEY='test-api-key')
    def test_generate_ai_recipes_empty_ingredients(self):
        """Test with no ingredients raises error."""
        # Empty ingredients should raise RuntimeError before calling API
        with self.assertRaises(RuntimeError) as context:
            generate_ai_recipes([])
        
        # Check that error message mentions ingredients
        self.assertIn('ingredient', str(context.exception).lower())
    
    @override_settings(OPENAI_API_KEY=None)
    def test_generate_ai_recipes_no_api_key(self):
        """Test error when API key is not configured."""
        with self.assertRaises(RuntimeError) as context:
            generate_ai_recipes(['chicken'])
        
        self.assertIn('OPENAI_API_KEY is not configured', str(context.exception))
    
    @override_settings(OPENAI_API_KEY='test-api-key')
    @patch('buddy_crocker.ai_recipe_service.OpenAI')
    def test_generate_ai_recipes_api_error(self, mock_openai_class):
        """Test handling of API errors."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception('API Error')
        
        with self.assertRaises(RuntimeError) as context:
            generate_ai_recipes(['chicken'])
        
        # Your code wraps errors with "Failed to generate recipes"
        self.assertIn('Failed to generate recipes', str(context.exception))
    
    @override_settings(OPENAI_API_KEY='test-api-key')
    @patch('buddy_crocker.ai_recipe_service.OpenAI')
    def test_generate_ai_recipes_invalid_json(self, mock_openai_class):
        """Test handling of invalid JSON response."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Return invalid JSON
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(
            message=MagicMock(
                content='This is not valid JSON'
            )
        )]
        mock_client.chat.completions.create.return_value = mock_response
        
        with self.assertRaises(RuntimeError) as context:
            generate_ai_recipes(['chicken'])
        
        self.assertIn('Failed to generate recipes', str(context.exception))
