"""
Management command to seed the database with popular recipes.

Usage:
    Note: Must use:
    python manage.py seed_allergens
    first

    python manage.py seed_recipes
    python manage.py seed_recipes --mode=refresh
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from buddy_crocker.models import Recipe, Ingredient, Allergen, RecipeIngredient
from services import usda_api, usda_service

User = get_user_model()

class Command(BaseCommand):
    """
    Management command to seed the database with popular recipes.

    Usage:
        python manage.py seed_recipes
        python manage.py seed_recipes --mode=refresh
    """
    help = 'Populate database with popular recipes and related information'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mode',
            type=str,
            default='update',
            choices=['update', 'refresh'],
            help='update: Add/update recipes | refresh: Clear and re-seed'
        )

    def handle(self, *args, **options):
        mode = options['mode']

        if mode == 'refresh':
            self.stdout.write(self.style.WARNING('Clearing existing recipes...'))
            Recipe.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Cleared all recipes'))

        # Create the authors for seeded recipes
        default_author, _ = User.objects.get_or_create(
            username='Food Network Kitchen',
            defaults={
                'first_name': 'Food',
                'last_name': 'Network',
                'email': 'foodnetwork@buddycrocker.com',
                'is_staff': True,
            }
        )
        ree_drummond_user = User.objects.get_or_create(
            username='Ree Drummond',
            defaults={
                'first_name': 'Ree',
                'last_name': 'Drummond',
                'email': 'reedrummond@buddycrocker.com',
                'is_staff': True,
            }
        )
        raechel_ray_user = User.objects.get_or_create(
            username='Rachael Ray',
            defaults={
                'first_name': 'Rachael',
                'last_name': 'Ray',
                'email': 'rachaelray@buddycrocker.com',
                'is_staff': True,
            }
        )
        tyler_florence_user = User.objects.get_or_create(
            username='Tyler Florence',
            defaults={
                'first_name': 'Tyler',
                'last_name': 'Florence',
                'email': 'tylerflorence@buddycrocker.com',
                'is_staff': True,
            }
        )

        # Create temporary ingredients for recipes
        temp_ingredients = [
            #Pizza
            {'name': 'pizza dough', 'search_term': 'pizza dough'},
            {'name': 'olive oil', 'search_term': 'olive oil'},
            {'name': 'pizza sauce', 'search_term': 'pizza sauce'},
            {'name': 'pepperoni', 'search_term': 'pepperoni'},
            {'name': 'mozzarella pearls', 'search_term': 'mozzarella pearls'},
            {'name': 'basil', 'search_term': 'basil'},

            #Spaghetti
            {'name': 'spaghetti', 'search_term': 'spaghetti'},
            {'name': 'salt', 'search_term': 'salt'},
            {'name': 'ground sirloin', 'search_term': 'ground sirloin'},
            {'name': 'worcestershire sauce', 'search_term': 'warcestershire sauce'},
            {'name': 'egg', 'search_term': 'egg'},
            {'name': 'italian bread crumbs', 'search_term': 'italian bread crumbs'},
            {'name': 'grated parmesan', 'search_term': 'grated parmesan'},
            {'name': 'garlic', 'search_term': 'garlic'},
            {'name': 'crushed red pepper flakes', 'search_term': 'crushed red pepper flakes'},
            {'name': 'onion', 'search_term': 'onion'},
            {'name': 'beef stock', 'search_term': 'beef stock'},
            {'name': 'crushed tomatoes', 'search_term': 'crushed tomatoes'},
            {'name': 'chopped parsley', 'search_term': 'chopped parsley'},
            {'name': 'garlic bread', 'search_term': 'garlic bread'},

            #Fried Rice
            {'name': 'shiitake mushrooms', 'search_term': 'shiitake mushrooms'},
            {'name': 'peanut oil', 'search_term': 'peanut oil'},
            {'name': 'scallions', 'search_term': 'scallions'},
            {'name': 'carrot', 'search_term': 'carrot'},
            {'name': 'red chile flakes', 'search_term': 'red chile flakes'},
            {'name': 'ginger', 'search_term': 'ginger'},
            {'name': 'soy sauce', 'search_term': 'soy sauce'},
            {'name': 'toasted sesame oil', 'search_term': 'toasted sesame oil'},
            {'name': 'cooked long-grain rice', 'search_term': 'cooked long-grain rice'},
            {'name': 'cooked chicken', 'search_term': 'cooked chicken'},
            {'name': 'frozen peas', 'search_term': 'frozen peas'},

            #Fish and Chips
            {'name': 'vegetable oil', 'search_term': 'vegetable oil'},
            {'name': 'russet potatoes', 'search_term': 'russet potatoes'},
            {'name': 'rice flour', 'search_term': 'rice flour'},
            {'name': 'baking powder', 'search_term': 'baking powder'},
            {'name': 'salt', 'search_term': 'salt'},
            {'name': 'pepper', 'search_term': 'pepper'},
            {'name': 'soda water', 'search_term': 'soda water'},
            {'name': 'cod fillets', 'search_term': 'cod fillets'},
            {'name': 'malt vinegar', 'search_term': 'malt vinegar'},

            #Chicken Enchiladas
            {'name': 'chicken breast', 'search_term': 'chicken breast'},
            {'name': 'cumin powder', 'search_term': 'cumin powder'},
            {'name': 'garlic powder', 'search_term': 'garlic powder'},
            {'name': 'mexican spice blend', 'search_term': 'mexican spice blend'},
            {'name': 'red onion', 'search_term': 'red onion'},
            {'name': 'frozen corn', 'search_term': 'frozen corn'},
            {'name': 'canned whole green chiles', 'search_term': 'canned whole green chiles'},
            {'name': 'canned chipotle chiles', 'search_term': 'canned chipotle chiles'},
            {'name': 'can stewed tomatoes', 'search_term': 'can stewed tomatoes'},
            {'name': 'all-purpose flour', 'search_term': 'all-purpose flour'},
            {'name': 'corn tortillas', 'search_term': 'corn tortillas'},
            {'name': 'enchilada sauce', 'search_term': 'enchilada sauce'},
            {'name': 'shredded cheddar cheese', 'search_term': 'shredded cheddar cheese'},
            {'name': 'shredded jack cheese', 'search_term': 'shredded jack cheese'},
            {'name': 'chopped cilantro leaves', 'search_term': 'chopped cilantro leaves'},
        ]

        self.stdout.write(self.style.MIGRATE_HEADING('\nFetching ingredients from USDA API:'))
        created_ingredients = []
        allergen_objects = Allergen.objects.all()

        for ing_data in temp_ingredients:
            try:
                self.stdout.write(f'  Searching for: {ing_data["name"]}...')
                search_results = usda_service.search_usda_foods(
                    ing_data['search_term'],
                    allergen_objects,
                    page_size=1
                )

                if not search_results:
                    self.stdout.write(
                        self.style.WARNING(
                            f'    ⚠ No results found for {ing_data["name"]}, skipping'
                        )
                    )
                    continue

                usda_result = search_results[0]
                fdc_id = usda_result.get('fdc_id')

                if not fdc_id:
                    self.stdout.write(
                        self.style.WARNING(
                            f'    ⚠ No FDC ID for {ing_data["name"]}, skipping'
                        )
                    )
                    continue

                complete_data = usda_service.get_complete_ingredient_data(
                    fdc_id,
                    allergen_objects
                )

                ingredient, created = Ingredient.objects.get_or_create(
                    name=ing_data['name'],
                    brand=complete_data['basic']['brand'] or 'Generic',
                    defaults={
                        'calories': int(complete_data['basic']['calories_per_100g']),
                        'fdc_id': fdc_id,
                        'nutrition_data': complete_data['nutrients'],
                        'portion_data': complete_data['portions']
                    }
                )

                for allergen_info in complete_data.get('detected_allergens', []):
                    try:
                        allergen = Allergen.objects.get(id=allergen_info['id'])
                        ingredient.allergens.add(allergen)
                    except Allergen.DoesNotExist:
                        pass

                if created:
                    created_ingredients.append(ingredient)
                    allergen_count = ingredient.allergens.count()
                    allergen_info = f' ({allergen_count} allergens)' if allergen_count > 0 else ''
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'    ✓ Created: {ingredient.name} '
                            f'[{int(ingredient.calories)} cal]{allergen_info}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'    ↻ Already exists: {ingredient.name}')
                    )

            except usda_api.USDAAPIKeyError:
                self.stdout.write(
                    self.style.ERROR('    ✗ USDA API Key Error - check your configuration')
                )
                self.stdout.write(
                    self.style.WARNING('Aborting ingredient fetch from USDA')
                )
                break

            except usda_api.USDAAPIRateLimitError:
                self.stdout.write(
                    self.style.WARNING(
                        f'    ⚠ Rate limit reached at {ing_data["name"]}'
                    )
                )
                self.stdout.write(
                    self.style.WARNING('Skipping remaining USDA lookups')
                )
                break

            except usda_api.USDAAPIError as e:
                self.stdout.write(
                    self.style.WARNING(
                        f'    ⚠ API error for {ing_data["name"]}: {str(e)}'
                    )
                )
                continue

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'    ✗ Unexpected error for {ing_data["name"]}: {str(e)}'
                    )
                )
                continue

        # Recipes to be added with ingredient details
        popular_recipes = [
            {
                'title': 'Cast-Iron Pizza',
                'author_username': 'Ree Drummond',
                'servings': 4,
                'prep_time': 15,
                'cook_time': 14,
                'difficulty': 'easy',
                'ingredients': [
                    {'name': 'pizza dough', 'amount': 1, 'unit': 'whole', 'notes': '14-inch circle', 'gram_weight': 450},
                    {'name': 'olive oil', 'amount': 2, 'unit': 'tbsp', 'notes': 'divided', 'gram_weight': 27},
                    {'name': 'pizza sauce', 'amount': 0.5, 'unit': 'cup', 'notes': '', 'gram_weight': 125},
                    {'name': 'pepperoni', 'amount': 3, 'unit': 'oz', 'notes': '', 'gram_weight': 85},
                    {'name': 'mozzarella pearls', 'amount': 1, 'unit': 'cup', 'notes': '', 'gram_weight': 150},
                    {'name': 'basil', 'amount': 0.25, 'unit': 'cup', 'notes': 'torn, for topping', 'gram_weight': 6},
                ],
                'instructions': (
                    '1. Place a 12-inch cast-iron skillet in the oven and preheat to 500 degrees F.\n'

                    '2. Meanwhile, roll or stretch the dough into a 14-inch circle. '
                    'Carefully remove the skillet from the oven. Drizzle two thirds of the olive oil into the skillet, '
                    'then carefully transfer the dough to the skillet, pressing the dough up the edges. '
                    'Spread the sauce over the dough, making sure to get all the way to the edges. '
                    'Shingle the pepperoni over the sauce and top with the mozzarella pearls. '
                    'Brush the exposed dough with the remaining olive oil. '
                    'Bake on the bottom rack until golden brown, 12 to 14 minutes.\n'

                    '3. Transfer to a cutting board, top with torn basil, cut into slices and serve.'
                )
            },
            {
                'title': 'Spaghetti and Meatballs',
                'author_username': 'Rachael Ray',
                'servings': 4,
                'prep_time': 15,
                'cook_time': 20,
                'difficulty': 'easy',
                'ingredients': [
                    {'name': 'spaghetti', 'amount': 1, 'unit': 'pound', 'notes': '', 'gram_weight': 0},
                    {'name': 'salt', 'amount': 1, 'unit': '', 'notes': 'for pasta water and meatballs', 'gram_weight': 0},
                    {'name': 'ground sirloin', 'amount': 1.25, 'unit': 'pounds', 'notes': '', 'gram_weight': 0},
                    {'name': 'worcestershire sauce', 'amount': 2, 'unit': 'tbsp', 'notes': 'eyeball it', 'gram_weight': 0},
                    {'name': 'egg', 'amount': 1, 'unit': '', 'notes': 'beaten', 'gram_weight': 0},
                    {'name': 'italian bread crumbs', 'amount': 0.5, 'unit': 'cup', 'notes': 'a couple of handfuls', 'gram_weight': 0},
                    {'name': 'grated parmesan', 'amount': 0.25, 'unit': 'cup', 'notes': '', 'gram_weight': 0},
                    {'name': 'garlic', 'amount': 6, 'unit': 'cloves', 'notes': '4 cloves crushed', 'gram_weight': 0},
                    {'name': 'pepper', 'amount': 1, 'unit': '', 'notes': 'for meatballs', 'gram_weight': 0},
                    {'name': 'olive oil', 'amount': 2, 'unit': 'turns of the pan', 'notes': '', 'gram_weight': 0},
                    {'name': 'crushed red pepper flakes', 'amount': 0.5, 'unit': 'tbsp', 'notes': '', 'gram_weight': 0},
                    {'name': 'onion', 'amount': 1, 'unit': '', 'notes': 'finely chopped', 'gram_weight': 0},
                    {'name': 'beef stock', 'amount': 1, 'unit': 'cup', 'notes': '', 'gram_weight': 0},
                    {'name': 'crushed tomatoes', 'amount': 1, 'unit': 'can', 'notes': '28 ounces', 'gram_weight': 0},
                    {'name': 'chopped parsley', 'amount': 1, 'unit': 'a handful', 'notes': 'chopped, flat-leaf', 'gram_weight': 0},
                    {'name': 'basil', 'amount': 10, 'unit': 'leaves', 'notes': 'torn, or thinly sliced', 'gram_weight': 0},
                    {'name': 'garlic bread', 'amount': 1, 'unit': '', 'notes': 'for the table', 'gram_weight': 0},
                ],
                'instructions': (
                    '''1. Preheat oven to 425 degrees F.\n'''

                    '''2. Place a large pot of water on to boil for spaghetti.
                    When it boils, add salt and pasta and cook to al dente.\n'''

                    '''3. Mix beef and Worcestershire, egg, bread crumbs, cheese,
                    garlic, salt and pepper. Roll meat into 1 1/2 inch medium-sized
                    meatballs and place on nonstick cookie sheet or a cookie sheet greased
                    with extra-virgin olive oil. Bake balls 10 to 12 minutes, until no longer pink.'''
                    '''4. Heat a deep skillet or medium pot over moderate heat.
                    Add oil, crushed pepper, garlic and finely chopped onion. Saute 5 to 7 minutes,
                    until onion bits are soft. Add beef stock, crushed tomatoes, and herbs.
                    Bring to a simmer and cook for about 10 minutes.'''
                    '''5. Toss hot, drained pasta with a few ladles of the sauce and grated cheese.
                    Turn meatballs in remaining sauce. Place pasta on dinner plates and top with meatballs
                    and sauce and extra grated cheese. Serve with bread or garlic bread (and some good chianti!)'''
                )
            },
            {
                'title': 'Fried Rice',
                'author_username': 'Food Network Kitchen',
                'servings': 4,
                'prep_time': 20,
                'cook_time': 30,
                'difficulty': 'medium',
                'ingredients': [
                    {'name': 'shiitake mushrooms', 'amount': 8, 'unit': 'dried', 'notes': '', 'gram_weight': 0},
                    {'name': 'peanut oil', 'amount': 3, 'unit': 'tbsp', 'notes': '', 'gram_weight': 0},
                    {'name': 'egg', 'amount': 2, 'unit': '', 'notes': 'lightly beaten with a pinch of salt', 'gram_weight': 0},
                    {'name': 'scallions', 'amount': 4, 'unit': 'white and green', 'notes': 'thinly sliced', 'gram_weight': 0},
                    {'name': 'carrot', 'amount': 0.25, 'unit': 'cup', 'notes': 'minced', 'gram_weight': 0},
                    {'name': 'garlic', 'amount': 1, 'unit': 'large clove', 'notes': 'minced', 'gram_weight': 0},
                    {'name': 'red chile flakes', 'amount': 1, 'unit': 'pinch', 'notes': '', 'gram_weight': 0},
                    {'name': 'ginger', 'amount': 1, 'unit': 'tbsp', 'notes': 'minced, peeled', 'gram_weight': 0},
                    {'name': 'soy sauce', 'amount': 2, 'unit': 'tbsp', 'notes': '', 'gram_weight': 0},
                    {'name': 'toasted sesame oil', 'amount': 1, 'unit': 'tbsp', 'notes': '', 'gram_weight': 0},
                    {'name': 'cooked long-grain rice', 'amount': 3, 'unit': 'cups', 'notes': '', 'gram_weight': 0},
                    {'name': 'cooked chicken', 'amount': 1, 'unit': 'cup', 'notes': '1/2 inch cubes', 'gram_weight': 0},
                    {'name': 'frozen peas', 'amount': 0.5, 'unit': 'cup', 'notes': 'defrosted in a strainer at room temperature', 'gram_weight': 0},

                ],
                'instructions': (
                    '''1. Put the mushrooms in a small bowl and cover with boiling water and
                    soak until re-hydrated, about 20 minutes. Drain, squeeze dry, and cut mushrooms
                    in quarters. Set aside.\n'''

                    '''2. Heat 1 tablespoon of the peanut oil in a well-seasoned
                    wok or large non-stick skillet over medium-high heat. Swirl to coat the pan.
                    Pour in the eggs, swirl the pan so the egg forms a large thin pancake.
                    (Lift the edge of the egg to allow any uncooked egg to run to the center.)
                    As soon as the egg has set, turn it out of the pan onto a cutting board.
                    Cool, cut into 1 inch pieces.\n'''

                    '''3. Wipe out the pan with a paper towel and heat the remaining peanut oil
                    over high heat. Add the scallions and carrots and stir-fry for 1 1/2 minutes.
                    Add the mushrooms, garlic, chile, and ginger, stir-fry for 1 minute more.
                    Add the soy sauce, sesame oil and rice and stir-fry for 2 to 3 minutes.
                    Add the meat, peas, and reserved egg, cook, stirring until heated through, about 2 to 3 minutes.
                    Serve immediately.'''
                )
            },
        ]

        # Seed popular recipes
        created_count = 0
        updated_count = 0

        self.stdout.write(self.style.MIGRATE_HEADING('\nSeeding Popular Recipes:'))
        for recipe_data in popular_recipes:
            try:
                author = User.objects.get(username=recipe_data['author_username'])
            except User.DoesNotExist:
                author = default_author

            recipe, created = Recipe.objects.get_or_create(
                title=recipe_data['title'],
                author=author,
                defaults={
                    'instructions': recipe_data['instructions'],
                    'servings': recipe_data.get('servings', 4),
                    'prep_time': recipe_data.get('prep_time'),
                    'cook_time': recipe_data.get('cook_time'),
                    'difficulty': recipe_data.get('difficulty', 'medium'),
                }
            )

            if not created:
                recipe.instructions = recipe_data['instructions']
                recipe.servings = recipe_data.get('servings', 4)
                recipe.prep_time = recipe_data.get('prep_time')
                recipe.cook_time = recipe_data.get('cook_time')
                recipe.difficulty = recipe_data.get('difficulty', 'medium')
                recipe.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'  ↻ Updated: {recipe.title}')
                )
            else:
                created_count += 1

            # Clear existing recipe ingredients
            RecipeIngredient.objects.filter(recipe=recipe).delete()

            # Add ingredients using RecipeIngredient through model
            ingredients_added = 0
            for idx, ingredient_data in enumerate(recipe_data['ingredients']):
                try:
                    ingredient = Ingredient.objects.filter(
                        name__iexact=ingredient_data['name']
                    ).first()

                    if ingredient:
                        recipe_ingredient = RecipeIngredient.objects.create(
                            recipe=recipe,
                            ingredient=ingredient,
                            amount=ingredient_data['amount'],
                            unit=ingredient_data['unit'],
                            notes=ingredient_data.get('notes', ''),
                             gram_weight=ingredient_data.get('gram_weight'),  # HARDCODED VALUE
                            order=idx
                        )
                        # Try to auto-calculate gram weight from USDA data
                        recipe_ingredient.auto_calculate_gram_weight()
                        recipe_ingredient.save()

                        ingredients_added += 1
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f'    ⚠ Ingredient not found: {ingredient_data["name"]}'
                            )
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'    ✗ Error adding ingredient {ingredient_data["name"]}: {str(e)}'
                        )
                    )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ Created: {recipe.title} ({ingredients_added} ingredients)'
                    )
                )

        # Summary
        self.stdout.write(self.style.SUCCESS('\n✓ Seeding complete!'))
        self.stdout.write(f'  Created: {created_count} recipes')
        self.stdout.write(f'  Updated: {updated_count} recipes')
        self.stdout.write(f'  Total: {Recipe.objects.count()} recipes in database')
