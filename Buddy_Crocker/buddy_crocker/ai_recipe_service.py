"""Service for generating recipes using OpenAI."""
from typing import Any, Dict, List
import json
import logging
import re
from openai import OpenAI
from django.conf import settings

logger = logging.getLogger(__name__)


def generate_ai_recipes(ingredients: List[str]) -> List[Dict[str, Any]]:
    """
    Generate 4 recipes using OpenAI: 2 with only pantry, 2 with extras.

    Args:
        ingredients: List of ingredient names from user's pantry

    Returns:
        List of recipe dicts with title, ingredients, instructions, uses_only_pantry

    Raises:
        RuntimeError: If API key is not configured or API call fails
    """
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    pantry_list = ", ".join(sorted(set(ingredients)))

    system_prompt = (
        "You are a recipe generator. Respond ONLY with valid JSON. "
        "Return exactly 4 recipes in this format: "
        '{"recipes": [{"title": "...", "ingredients": ["1 cup flour", "2 eggs"], '
        '"instructions": "1. Step one\\n2. Step two", "uses_only_pantry": true}]}'
    )

    user_prompt = (
        f"Using these pantry ingredients: {pantry_list}. "
        "Generate exactly 4 recipes. "
        "2 recipes must use ONLY the pantry ingredients (uses_only_pantry: true). "
        "2 recipes can suggest additional ingredients not in pantry (uses_only_pantry: false). "
        "Include specific amounts for each ingredient (e.g., '2 cups flour', '1 lb chicken'). "
        "Return as JSON with 'recipes' array."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=1500,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""
        logger.info("OpenAI response length: %d chars", len(content))
    except Exception as exc:
        logger.error("OpenAI API error: %s", exc)
        raise RuntimeError(f"Failed to generate recipes: {exc}") from exc

    if not content:
        raise RuntimeError("OpenAI returned empty response")

    # Parse JSON response
    try:
        data = json.loads(content)
        recipes = _extract_recipes(data)
        if len(recipes) >= 4:
            return recipes[:4]
        logger.warning("Only got %d recipes, padding with defaults", len(recipes))
        return recipes
    except json.JSONDecodeError as exc:
        logger.error("JSON parse error: %s. Content: %s", exc, content[:500])

        # Fallback: try to extract JSON array
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            try:
                recipes_list = json.loads(json_match.group(0))
                recipes = _extract_recipes({"recipes": recipes_list})
                if recipes:
                    return recipes[:4]
            except json.JSONDecodeError:
                pass

        raise RuntimeError("Failed to parse AI response") from exc


def _extract_recipes(data: Any) -> List[Dict[str, Any]]:
    """
    Extract recipe data from various JSON structures.

    Args:
        data: Parsed JSON from OpenAI (dict or list)

    Returns:
        List of validated recipe dictionaries
    """
    recipes = []

    # Handle different response structures
    if isinstance(data, dict):
        items = data.get("recipes", [])
    elif isinstance(data, list):
        items = data
    else:
        logger.warning("Unexpected data type: %s", type(data))
        return []

    for item in items:
        if not isinstance(item, dict):
            continue

        title = str(item.get("title", "")).strip()
        ingredients_raw = item.get("ingredients", [])
        instructions = str(item.get("instructions", "")).strip()
        uses_only_pantry = bool(item.get("uses_only_pantry", False))

        # Validate and clean ingredients
        ingredients = []
        for ing in ingredients_raw:
            cleaned = str(ing).strip()
            if cleaned:
                ingredients.append(cleaned)

        # Only add recipes with all required fields
        if title and instructions and ingredients:
            recipes.append({
                "title": title,
                "ingredients": ingredients,
                "instructions": instructions,
                "uses_only_pantry": uses_only_pantry,
            })

    logger.info("Extracted %d valid recipes", len(recipes))
    return recipes
