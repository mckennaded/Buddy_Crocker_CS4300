"""
Tests for the USDA API (Specifically the )

Utilizes the responses package to mock API calls
"""

import os
import sys
from unittest.mock import patch
from django.test import TestCase
from dotenv import load_dotenv
import responses
from requests.exceptions import ConnectionError, Timeout, HTTPError


# Mock API responses
MOCK_SEARCH_RESPONSE = {
    "foods": [
        {
            "description": "Cheddar Cheese",
            "dataType": "Branded",
            "fdcId": 123456,
            "brandOwner": "Generic Brand",
            "foodNutrients": [
                {"nutrientName": "Energy", "value": 403},
                {"nutrientName": "Protein", "value": 25}
            ]
        },
        {
            "description": "Sharp Cheddar Cheese",
            "dataType": "Branded",
            "fdcId": 123457,
            "brandOwner": "Brand X",
            "foodNutrients": [
                {"nutrientName": "Energy", "value": 410},
                {"nutrientName": "Protein", "value": 26}
            ]
        }
    ]
}

MOCK_FOOD_DETAILS_RESPONSE = {
    "fdcId": 1897574,
    "description": "Bacon, cooked",
    "dataType": "SR Legacy",
    "brandOwner": "USDA",
    "foodNutrients": [
        {
            "nutrient": {"name": "Energy", "id": 1008},
            "amount": 541
        },
        {
            "nutrient": {"name": "Protein", "id": 1003},
            "amount": 37.04
        }
    ]
}

MOCK_EMPTY_SEARCH_RESPONSE = {
    "foods": []
}


class SearchFoodsTest(TestCase):
    """Tests for the search_foods function"""

    def setUp(self):
        """Set up the API key and import the module."""
        # Get the path to the services directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        services_dir = os.path.join(current_dir, '..', '..', 'services')
        services_dir = os.path.abspath(services_dir)

        # Add it to sys.path if not already there
        if services_dir not in sys.path:
            sys.path.insert(0, services_dir)

        # Now import the module
        import usda_api
        self.usda_api = usda_api

        # Load the .env file and get the API key
        load_dotenv()
        self.API_KEY = os.getenv("USDA_API_KEY")

    @responses.activate
    def test_search_foods_success(self):
        """Test successful search_foods API call"""
        responses.add(
            responses.GET,
            'https://api.nal.usda.gov/fdc/v1/foods/search',
            json=MOCK_SEARCH_RESPONSE,
            status=200
        )

        foods = self.usda_api.search_foods("Cheddar Cheese", page_size=10)

        self.assertEqual(len(foods), 2)
        self.assertEqual(foods[0]["description"], "Cheddar Cheese")
        self.assertEqual(foods[0]["fdcId"], 123456)
        self.assertEqual(foods[1]["description"], "Sharp Cheddar Cheese")

    @responses.activate
    def test_search_foods_empty_results(self):
        """Test search_foods with no results"""
        responses.add(
            responses.GET,
            'https://api.nal.usda.gov/fdc/v1/foods/search',
            json=MOCK_EMPTY_SEARCH_RESPONSE,
            status=200
        )

        foods = self.usda_api.search_foods("NonexistentFood123")

        self.assertEqual(len(foods), 0)

    @responses.activate
    def test_search_foods_missing_calories(self):
        """Test search_foods when calories (Energy) nutrient is missing"""
        mock_response = {
            "foods": [
                {
                    "description": "Test Food",
                    "dataType": "Branded",
                    "fdcId": 999999,
                    "brandOwner": "Test Brand",
                    "foodNutrients": [
                        {"nutrientName": "Protein", "value": 25}
                    ]
                }
            ]
        }

        responses.add(
            responses.GET,
            'https://api.nal.usda.gov/fdc/v1/foods/search',
            json=mock_response,
            status=200
        )

        foods = self.usda_api.search_foods("Test Food")

        self.assertEqual(len(foods), 1)
        # Should handle missing Energy nutrient gracefully

    @responses.activate
    def test_search_foods_invalid_api_key(self):
        """Test search_foods with invalid API key"""
        responses.add(
            responses.GET,
            'https://api.nal.usda.gov/fdc/v1/foods/search',
            json={"error": {"message": "Invalid API key"}},
            status=403
        )

        with self.assertRaises(Exception):
            self.usda_api.search_foods("Cheddar Cheese")

    @responses.activate
    def test_search_foods_rate_limiting(self):
        """Test search_foods with rate limiting response"""
        responses.add(
            responses.GET,
            'https://api.nal.usda.gov/fdc/v1/foods/search',
            json={"error": {"message": "Rate limit exceeded"}},
            status=429
        )

        with self.assertRaises(Exception):
            self.usda_api.search_foods("Cheddar Cheese")

    @responses.activate
    def test_search_foods_network_error(self):
        """Test search_foods with network connection error"""
        responses.add(
            responses.GET,
            'https://api.nal.usda.gov/fdc/v1/foods/search',
            body=ConnectionError("Network error")
        )

        with self.assertRaises(ConnectionError):
            self.usda_api.search_foods("Cheddar Cheese")

    @responses.activate
    def test_search_foods_timeout(self):
        """Test search_foods with timeout"""
        responses.add(
            responses.GET,
            'https://api.nal.usda.gov/fdc/v1/foods/search',
            body=Timeout("Request timeout")
        )

        with self.assertRaises(Timeout):
            self.usda_api.search_foods("Cheddar Cheese")

    @responses.activate
    def test_search_foods_custom_page_size(self):
        """Test search_foods with custom page size parameter"""
        responses.add(
            responses.GET,
            'https://api.nal.usda.gov/fdc/v1/foods/search',
            json=MOCK_SEARCH_RESPONSE,
            status=200
        )

        foods = self.usda_api.search_foods("Cheddar Cheese", page_size=5)

        # Verify the request was made with correct page_size
        self.assertEqual(len(responses.calls), 1)
        self.assertIn('pageSize=5', responses.calls[0].request.url)


class GetFoodDetailsTest(TestCase):
    """Tests for the get_food_details function"""

    def setUp(self):
        """Set up the API key and import the module."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        services_dir = os.path.join(current_dir, '..', '..', 'services')
        services_dir = os.path.abspath(services_dir)

        if services_dir not in sys.path:
            sys.path.insert(0, services_dir)

        import usda_api
        self.usda_api = usda_api

        load_dotenv()
        self.API_KEY = os.getenv("USDA_API_KEY")

    @responses.activate
    def test_get_food_details_success(self):
        """Test successful get_food_details API call"""
        responses.add(
            responses.GET,
            'https://api.nal.usda.gov/fdc/v1/food/1897574',
            json=MOCK_FOOD_DETAILS_RESPONSE,
            status=200
        )

        # The function prints but doesn't return, so we just verify it doesn't crash
        self.usda_api.get_food_details(1897574)

        self.assertEqual(len(responses.calls), 1)

    @responses.activate
    def test_get_food_details_invalid_id(self):
        """Test get_food_details with invalid food ID"""
        responses.add(
            responses.GET,
            'https://api.nal.usda.gov/fdc/v1/food/999999999',
            json={"error": {"message": "Food not found"}},
            status=404
        )

        with self.assertRaises(Exception):
            self.usda_api.get_food_details(999999999)

    @responses.activate
    def test_get_food_details_missing_calories(self):
        """Test get_food_details when calories are missing"""
        mock_response = {
            "fdcId": 1897574,
            "description": "Test Food",
            "dataType": "SR Legacy",
            "brandOwner": "USDA",
            "foodNutrients": [
                {
                    "nutrient": {"name": "Protein", "id": 1003},
                    "amount": 37.04
                }
            ]
        }

        responses.add(
            responses.GET,
            'https://api.nal.usda.gov/fdc/v1/food/1897574',
            json=mock_response,
            status=200
        )

        # Should handle missing Energy nutrient gracefully
        self.usda_api.get_food_details(1897574)

    @responses.activate
    def test_get_food_details_network_error(self):
        """Test get_food_details with network error"""
        responses.add(
            responses.GET,
            'https://api.nal.usda.gov/fdc/v1/food/1897574',
            body=ConnectionError("Network error")
        )

        with self.assertRaises(ConnectionError):
            self.usda_api.get_food_details(1897574)

    @responses.activate
    def test_get_food_details_rate_limiting(self):
        """Test get_food_details with rate limiting"""
        responses.add(
            responses.GET,
            'https://api.nal.usda.gov/fdc/v1/food/1897574',
            json={"error": {"message": "Rate limit exceeded"}},
            status=429
        )

        with self.assertRaises(Exception):
            self.usda_api.get_food_details(1897574)