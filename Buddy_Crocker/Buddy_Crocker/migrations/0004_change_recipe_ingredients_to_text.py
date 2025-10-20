from django.db import migrations, models

def copy_m2m_to_text(apps, schema_editor):
    Recipe = apps.get_model("Buddy_Crocker", "Recipe")
    Ingredient = apps.get_model("Buddy_Crocker", "Ingredient")
    # Iterate recipes, collect ingredient names, and store as comma-separated text
    for recipe in Recipe.objects.all():
        names = []
        try:
            # M2M existed prior to this migration
            names = list(recipe.ingredients.values_list("name", flat=True))
        except Exception:
            names = []
        recipe.ingredients_text = ", ".join(names)
        recipe.save(update_fields=["ingredients_text"])

def noop_reverse(apps, schema_editor):
    # No reliable reverse from free text back to normalized M2M
    pass

class Migration(migrations.Migration):
    dependencies = [
        ("Buddy_Crocker", "0003_alter_recipe_ingredients"),
    ]

    operations = [
        # 1) Add a temporary text field
        migrations.AddField(
            model_name="recipe",
            name="ingredients_text",
            field=models.TextField(blank=True, default=""),
        ),
        # 2) Copy data from M2M into text
        migrations.RunPython(copy_m2m_to_text, noop_reverse),
        # 3) Drop the old M2M field (and its through table)
        migrations.RemoveField(
            model_name="recipe",
            name="ingredients",
        ),
        # 4) Rename temp text field to final name 'ingredients'
        migrations.RenameField(
            model_name="recipe",
            old_name="ingredients_text",
            new_name="ingredients",
        ),
    ]
