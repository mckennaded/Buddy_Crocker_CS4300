import os
from dotenv import load_dotenv
import requests

"""
Values from the API:
"description"   - The name of the food item
"dataType"      - The data type of the food item
"fdcId"         - The USDA Food ID of the food item
"brandOwner"    - The brand of the food
"foodNutrients" - The nutrients of the food
"nutrientName"  - The name of the nutrient (Energy is calories)
"value"         - The calorie count 
"""

"""
How to use:

Ensure that the USDA API key is in the .env file:
USDA_API_KEY = "your_key"

search_foods() prints the first 10 entries for the
inputed query in the "query" field

For each entry, the Description, Data Type, FDC ID, Brand, 
and Calories are returned
"""

#Load the .env file and get the API key
load_dotenv()
API_KEY = os.getenv("USDA_API_KEY")

#Search Foods Function
def search_foods(query, page_size=10):
    #Set up parameters for search
    url = 'https://api.nal.usda.gov/fdc/v1/foods/search'

    params = {
        "api_key": API_KEY,
        "query": query,
        "pageSize": page_size,
    }

    #Get the response from the API
    response = requests.get(url, params=params)
    data = response.json() #Convert to a python dictionary

    #Print out info
    foods = data["foods"]

    for food in foods:
        print("Description:", food["description"])
        print("Data Type:", food["dataType"])
        print("FDC ID:", food["fdcId"])
        print("Brand:", food.get("brandOwner", "N/A"))
        calories = next(
            (n["value"] for n in food["foodNutrients"] if n["nutrientName"] == "Energy"),
            None
        )
        print("Calories:", calories)
        print("-" * 40)

    return foods

def get_food_name(query, page_size=1):
    #Set up parameters for search
    url = 'https://api.nal.usda.gov/fdc/v1/foods/search'

    params = {
        "api_key": API_KEY,
        "query": query,
        "pageSize": page_size,
    }

    #Get the response from the API
    response = requests.get(url, params=params)
    data = response.json() #Convert to a python dictionary

    #Print out info
    foods = data["foods"]

    for food in foods:
        description = food["description"]
        print("Description:", food["description"])

    print("-" * 40)

    return description

#Test
#search_foods("Cheddar Cheese")
search_foods("Bacon")

get_food_name("Cheddar Cheese")
get_food_name("Bacon")