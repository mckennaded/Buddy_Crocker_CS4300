import os
from dotenv import load_dotenv
import requests
from requests.exceptions import RequestException, Timeout

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

#Error Handling

class USDAAPIError(Exception):
    """Base Error exception"""
    pass

class USDAAPIKeyError(USDAAPIError):
    """Exception for invalid API key"""
    pass

class USDAAPINotFoundError(USDAAPIError):
    """Exception for resource not found"""
    pass

class USDAAPIRateLimitError(USDAAPIError):
    """Exception for rate limiting"""
    pass

#Load the .env file and get the API key
load_dotenv()
API_KEY = os.getenv("USDA_API_KEY")

def _handle_response(response):
    """Function to handle API responses and output error messages"""

    #Check for HTTP error status codes
    if response.status_code == 403:
        raise USDAAPIKeyError("Invalid API key or access forbidden")
    elif response.status_code == 404:
        raise USDAAPINotFoundError("Resource not found")
    elif response.status_code == 429:
        raise USDAAPIRateLimitError("Rate limit exceeded. Please try again later")
    elif response.status_code >= 500:
        raise USDAAPIError(f"Server error: {response.status_code}")
    elif response.status_code != 200:
        raise USDAAPIError(f"API request failed with status {response.status_code}")

    #Try to parse JSON response
    try:
        data = response.json()
    except ValueError:
        raise USDAAPIError("Invalid JSON response from API")

    #Check if response contains an error field
    if 'error' in data:
        error_message = data['error'].get('message', 'Unknown error')
        raise USDAAPIError(f"API error: {error_message}")

    return data

#Search Foods Function
def search_foods(query, page_size=10):
    #Check that the API key is correct
    if not API_KEY:
        raise USDAAPIKeyError("USDA API key not found. Please set USDA_API_KEY in .env")

    #Set up parameters for search
    url = 'https://api.nal.usda.gov/fdc/v1/foods/search'

    params = {
        "api_key": API_KEY,
        "query": query,
        "pageSize": page_size,
    }

    try:
        #Get the response from the API
        response = requests.get(url, params=params, timeout=5)
        data = _handle_response(response) #Convert to a python dictionary
    #Timeout error
    except Timeout:
        raise USDAAPIError("Request timeout. Please try again")
    #Connection Error
    except ConnectionError:
        raise USDAAPIError("Network connection error. Please check your internet connection")
    #Request Exception error
    except RequestException as e:
        raise USDAAPIError(f"Request failed: {str(e)}")

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
    #Check that the API key is correct
    if not API_KEY:
        raise USDAAPIKeyError("USDA API key not found. Please set USDA_API_KEY in .env")

    #Set up parameters for search
    url = f'https://api.nal.usda.gov/fdc/v1/food/{fdc_Id}'

    params = {
        "api_key": API_KEY,
    }

    try:
        #Get the response from the API
        response = requests.get(url, params=params, timeout=5)
        food = _handle_response(response) #Convert to a python dictionary
    except Timeout:
        raise USDAAPIError("Request timeout. Please try again")
    except ConnectionError:
        raise USDAAPIError("Network connection error. Please check your internet connection")
    except RequestException as e:
        raise USDAAPIError(f"Request failed: {str(e)}")

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

    return food

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

    description = ""

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