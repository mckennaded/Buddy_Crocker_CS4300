import os
import re
from openai import OpenAI


def generate_ai_recipes(ingredient_names, allergens, api_key):
    """Generate recipes using OpenAI based on pantry ingredients and allergens."""
    client = OpenAI(api_key=api_key)
    prompt = (
        "Generate 2 recipes that can be made using only these ingredients: "
        f"{', '.join(ingredient_names)}. "
        "Then generate 2 more recipes that include these ingredients but require others. "
        f"Avoid allergens: {', '.join(allergens)}. "
        "Format recipes as:\nTitle: <title>\nIngredients:\n- <ingredient>\nInstructions:\n1. <step>\n"
        "Do not add markdown or extra formatting."
    )

    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful cooking assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    ai_text = response.choices[0].message.content
    return _parse_ai_response(ai_text)


def _parse_ai_response(ai_text):
    """Parse AI response text into structured recipe data."""
    recipes = []
    blocks = re.split(r"(?=Title: )", ai_text.strip())
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        title, ingredients, instructions = "", [], []
        lines = block.split("\n")
        mode = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.lower().startswith("title:"):
                title = line.replace("Title:", "").strip()
                continue
            if line.lower().startswith("ingredients:"):
                mode = "ingredients"
                continue
            if line.lower().startswith("instructions:"):
                mode = "instructions"
                continue
            if mode == "ingredients":
                ingredients.append(line.lstrip("- ").strip())
            elif mode == "instructions":
                instructions.append(line)
        if title:
            recipes.append(
                {
                    "title": title,
                    "ingredients": ingredients,
                    "instructions": "\n".join(instructions),
                }
            )
    return recipes
