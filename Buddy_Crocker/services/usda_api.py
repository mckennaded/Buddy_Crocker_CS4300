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
"value"         - The calorie count when searching with a name query
"amount"        - The calorie count when searching with a specific food ID
"""

"""
How to use:

Ensure that the USDA API key is in the .env file:
USDA_API_KEY = "your_key"

search_foods() prints the first 10 entries for the
inputed query in the "query" field

For each entry, the Description, Data Type, FDC ID, Brand, 
and Calories are returned

get_food_details() returns the details of the food
if there is a match in the fdc_Id
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

        #The calories are stored in the 'value' variable for the
        #'Energy' nutrient in name search queries
        calories = next(
            (nutrient["value"] for nutrient in food["foodNutrients"] if nutrient["nutrientName"] == "Energy"),
            None
        )
        print("Calories:", calories, 'kcal')
        print("-" * 40)

    return foods

def get_food_details(fdc_Id):
    #Set up parameters for search
    url = f'https://api.nal.usda.gov/fdc/v1/food/{fdc_Id}'

    params = {
        "api_key": API_KEY,
    }

    #Get the response from the API
    response = requests.get(url, params=params)
    food = response.json() #Convert to a python dictionary

    #Print out info
    print("Details for food ID:", fdc_Id)

    print("Description:", food.get('description'))
    print("Data Type:", food.get('dataType'))
    print("Brand:", food.get("brandOwner", "N/A"))
    
    #When searching by food ID, 'nutrient' has both a name
    # and an ID field, and calories are stored in 'amount'
    calories = 0
    for nutrient in food.get("foodNutrients", []):
        if nutrient.get('nutrient', {}).get('name') == "Energy":
            calories = nutrient.get('amount')
           
    print("Calories:", calories, "kcal")

    print("-" * 40)

    #Add error message if there was no match

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



#Tests

#search_foods("Cheddar Cheese")
#search_foods("Bacon")
#get_food_name("Cheddar Cheese")
#get_food_name("Bacon")
#get_food_details(1897574)