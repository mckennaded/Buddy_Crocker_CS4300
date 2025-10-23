#Test a single API Call

from django.test import TestCase
from django.db import IntegrityError
from ... #Fix import

#Load the .env file and get the API key
load_dotenv()
API_KEY = os.getenv("USDA_API_KEY")

#def test_food_search(self):
#        """Test that a food item can be searched."""
#        cheeseName = get_food_name("Cheddar Cheese")
#        self.assertEqual(cheeseName, "CHEDDAR CHEESE")