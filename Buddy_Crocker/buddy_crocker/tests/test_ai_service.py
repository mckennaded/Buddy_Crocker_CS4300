"""Tests for AI recipe generation service."""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from buddy_crocker.ai_recipe_service import generate_ai_recipes

class AIRecipeServiceTest(TestCase):
    """Test AI recipe generation."""
    
    @patch('buddy_crocker.ai_recipe_service.openai.ChatCompletion.create')
    def test_generate_ai_recipes_success(self, mock_openai):
        """Test successful recipe generation."""
        mock_openai.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content='[{"title": "Test Recipe", "ingredients": ["1 cup rice"], "instructions": "Cook rice"}]'
                )
            )]
        )
        
        recipes = generate_ai_recipes(['rice'])
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0]['title'], 'Test Recipe')
    
    def test_generate_ai_recipes_empty_ingredients(self):
        """Test with no ingredients."""
        with self.assertRaises(ValueError):
            generate_ai_recipes([])
