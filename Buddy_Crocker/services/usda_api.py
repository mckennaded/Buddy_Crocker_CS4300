import os
from dotenv import load_dotenv
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError
from django.core.cache import cache
import hashlib
import json
from datetime import datetime

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

#Load the .env file at module level
load_dotenv()

def _get_api_key():
    """Get the API key from environment variables"""
    return os.getenv("USDA_API_KEY")

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

def _generate_cache_key(prefix, **kwargs):
    """Generate a unique cache key based on function parameters"""
    # Sort kwargs to ensure consistent key generation
    sorted_params = sorted(kwargs.items())
    param_str = json.dumps(sorted_params, sort_keys=True)
    hash_obj = hashlib.md5(param_str.encode())
    return f"usda_{prefix}_{hash_obj.hexdigest()}"

#Search Foods Function
def search_foods(query, page_size=10, use_cache=True):
    #Create a Cache Key (Acts as a specific area of the cache to only store search queries)
    #Cache key is recreated every function call to prepare the new data to be added to the cache
    #No data is actually added to the cache here
    cache_key = _generate_cache_key('search', query=query, page_size=page_size)

    #Try to get from cache first
    if use_cache:
        #Get the data from the cache key if the data is already in it
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            print(f"[CACHE HIT] Retrieved '{query}' from cache")
            return cached_data

    #Get the API key dynamically
    API_KEY = _get_api_key()
    
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
    #Timeout error (Occurs during response creation)
    except Timeout:
        raise
    #Connection Error (Occurs during response creation)
    except ConnectionError:
        raise
    #Request Exception error (Occurs during response creation)
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

    #Log the API call
    file_path = "services/usda_api_log.txt"
    current_datetime = str(datetime.now())

    #Write or append the call to the file
    with open(file_path, 'a') as log:
        log.write(current_datetime)
        log.write(" | Searched USDA API with query: ")
        log.write(query)
        log.write(" with API call ")
        log.write(url)
        log.write("\n")

    # Store in cache
    if use_cache:
        #After the new cache key has been prepared with new information
        #cache.set actualizes the new information into the cache
        #Only occurs if there is new data to be stored
        cache.set(cache_key, foods, timeout=2592000)  # Cache for 30 days
        print(f"[CACHE MISS] Stored '{query}' in cache")

    return foods

def get_food_details(fdc_Id, use_cache=True):
    #Create a Cache Key
    cache_key = _generate_cache_key('details', fdc_id=fdc_Id)

    # Try to get from cache first
    if use_cache:
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            print(f"[CACHE HIT] Retrieved food ID {fdc_Id} from cache")
            return cached_data

    #Get the API key dynamically
    API_KEY = _get_api_key()
    
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

        # Check for a ValueError before checking status codes
        # This allows KeyError to be raised when accessing missing fields
        if response.status_code == 404:
            try:
                data = response.json()
            except ValueError:
                raise USDAAPIError("Invalid JSON response from API")
        else:
            data = _handle_response(response) #Convert to a python dictionary
    #These errors occur during response creation
    except Timeout:
        raise
    except ConnectionError:
        raise
    except RequestException as e:
        raise USDAAPIError(f"Request failed: {str(e)}")
    
    food = data

    #Print out info
    print("Details for food ID:", fdc_Id)

    print("Description:", food['description'])  # Will raise KeyError if error response
    print("Data Type:", food['dataType'])
    print("Brand:", food.get("brandOwner", "N/A"))
    
    #When searching by food ID, 'nutrient' has both a name
    # and an ID field, and calories are stored in 'amount'
    calories = 0
    for nutrient in food.get("foodNutrients", []):
        if nutrient.get('nutrient', {}).get('name') == "Energy":
            calories = nutrient.get('amount')
           
    print("Calories:", calories, "kcal")

    print("-" * 40)

    #Log the API call
    file_path = "services/usda_api_log.txt"
    current_datetime = str(datetime.now())

    #Write or append the call to the file
    with open(file_path, 'a') as log:
        log.write(current_datetime)
        log.write(" | Retrieved details for food ID: ")
        log.write(str(fdc_Id))
        log.write(" with API call ")
        log.write(url)
        log.write("\n")

    # Store in cache
    if use_cache:
        cache.set(cache_key, food, timeout=2592000)  # Cache for 30 days
        print(f"[CACHE MISS] Stored food ID {fdc_Id} in cache")

    return food

def get_food_name(query, page_size=1):
    #Get the API key dynamically
    API_KEY = _get_api_key()
    
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