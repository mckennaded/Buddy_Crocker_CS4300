import os
from dotenv import load_dotenv
import requests

#Load the environment to get the API key
load_dotenv()

#Search Foods Function
def search_foods(query, page_size=10):
    #Set up parameters for search
    API_KEY = os.getenv("USDA_API_KEY")
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
        print("Data type", food["dataType"])
        print("FDC ID:", food["fdcId"])
        print("Brand:", food.get("brandOwner", "N/A"))
        print("Nutrients:")
        for nutrient in food.get("foodNutrients", []):
            print(f"  - {nutrient['nutrientName']}: {nutrient['value']} {nutrient['unitName']}")
        print("-" * 40)

#Test
search_foods("Cheddar Cheese")