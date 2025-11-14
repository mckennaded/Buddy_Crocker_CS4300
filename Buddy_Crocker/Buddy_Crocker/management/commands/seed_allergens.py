"""
Management command to seed the database with FDA Major 9 allergens and dietary preferences.

Usage:
    python manage.py seed_allergens
    python manage.py seed_allergens --mode=refresh
"""
from django.core.management.base import BaseCommand
from Buddy_Crocker.models import Allergen


class Command(BaseCommand):
    help = 'Populate database with FDA Major 9 allergens and dietary preferences'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mode',
            type=str,
            default='update',
            choices=['update', 'refresh'],
            help='update: Add/update allergens | refresh: Clear and re-seed'
        )

    def handle(self, *args, **options):
        mode = options['mode']

        if mode == 'refresh':
            self.stdout.write(self.style.WARNING('Clearing existing allergens...'))
            Allergen.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Cleared all allergens'))

        # FDA Major 9 Allergens
        fda_allergens = [
            {
                'name': 'Milk',
                'category': 'fda_major_9',
                'alternative_names': [
                    'dairy', 'lactose', 'casein', 'whey',
                    'cream', 'butter', 'cheese', 'yogurt'
                ],
                'description': 'Milk and dairy products from cows, goats, and other mammals',
                'usda_search_terms': [
                    'milk', 'dairy', 'lactose', 'casein',
                    'whey', 'cream', 'butter', 'cheese'
                ]
            },
            {
                'name': 'Eggs',
                'category': 'fda_major_9',
                'alternative_names': [
                    'egg', 'albumin', 'ovalbumin', 'egg white',
                    'egg yolk', 'mayonnaise'
                ],
                'description': 'Eggs and egg-containing products',
                'usda_search_terms': ['egg', 'albumin', 'ovalbumin', 'mayonnaise']
            },
            {
                'name': 'Fish',
                'category': 'fda_major_9',
                'alternative_names': [
                    'seafood', 'finned fish', 'salmon', 'tuna', 'cod',
                    'halibut', 'tilapia'
                ],
                'description': 'Fish with fins (salmon, tuna, cod, etc.)',
                'usda_search_terms': [
                    'fish', 'salmon', 'tuna', 'cod', 'halibut',
                    'tilapia', 'anchovy'
                ]
            },
            {
                'name': 'Shellfish',
                'category': 'fda_major_9',
                'alternative_names': [
                    'crustacean', 'mollusk', 'shrimp', 'crab', 'lobster',
                    'clam', 'oyster', 'mussel', 'scallop'
                ],
                'description': ('Crustaceans (shrimp, crab, lobster) '
                    'and mollusks (clams, oysters)'),
                'usda_search_terms': [
                    'shrimp', 'crab', 'lobster', 'clam', 'oyster',
                    'mussel', 'scallop', 'crayfish'
                ]
            },
            {
                'name': 'Tree Nuts',
                'category': 'fda_major_9',
                'alternative_names': [
                    'almond', 'walnut', 'cashew', 'pecan', 'pistachio',
                    'macadamia', 'hazelnut', 'brazil nut'
                ],
                'description': ('Tree nuts including almonds, '
                    'walnuts, cashews, pecans, and more'),
                'usda_search_terms': [
                    'almond', 'walnut', 'cashew', 'pecan', 'pistachio',
                    'macadamia', 'hazelnut'
                ]
            },
            {
                'name': 'Peanuts',
                'category': 'fda_major_9',
                'alternative_names': [
                    'peanut', 'groundnut', 'peanut butter','arachis'
                ],
                'description': 'Peanuts and peanut-containing products',
                'usda_search_terms': ['peanut', 'groundnut', 'arachis']
            },
            {
                'name': 'Wheat',
                'category': 'fda_major_9',
                'alternative_names': [
                    'gluten', 'flour', 'wheat flour', 'whole wheat', 
                    'durum', 'semolina', 'spelt'
                ],
                'description': 'Wheat and wheat-containing products (primary source of gluten)',
                'usda_search_terms': [
                    'wheat', 'flour', 'gluten', 'durum', 'semolina', 'spelt'
                ]
            },
            {
                'name': 'Soybeans',
                'category': 'fda_major_9',
                'alternative_names': [
                    'soy', 'soya', 'tofu', 'edamame', 'soy sauce', 'tempeh', 'miso'
                ],
                'description': 'Soybeans and soy-containing products',
                'usda_search_terms': ['soy', 'soya', 'tofu', 'edamame', 'tempeh', 'miso']
            },
            {
                'name': 'Sesame',
                'category': 'fda_major_9',
                'alternative_names': ['tahini', 'sesame seed', 'sesame oil', 'sesamol'],
                'description': 'Sesame seeds and sesame-containing products',
                'usda_search_terms': ['sesame', 'tahini', 'sesamol']
            },
        ]

        # Dietary Preferences
        dietary_preferences = [
            {
                'name': 'Meat',
                'category': 'dietary_preference',
                'alternative_names': [
                    'beef', 'pork', 'chicken', 'lamb', 'poultry', 'turkey', 'duck', 'veal'
                ],
                'description': 'All meat products for vegetarian filtering',
                'usda_search_terms': [
                    'beef', 'pork', 'chicken', 'lamb', 'turkey', 'duck', 'veal', 'meat'
                ]
            },
            {
                'name': 'Animal Products',
                'category': 'dietary_preference',
                'alternative_names': ['meat', 'dairy', 'eggs', 'honey', 'gelatin', 'animal'],
                'description': 'All animal-derived products for vegan filtering',
                'usda_search_terms': ['meat', 'dairy', 'egg', 'honey', 'gelatin']
            },
            {
                'name': 'Pork',
                'category': 'dietary_preference',
                'alternative_names': [
                    'pork', 'bacon', 'ham', 'pork chop', 'sausage', 'prosciutto'
                ],
                'description': 'Pork products for Halal/Kosher dietary restrictions',
                'usda_search_terms': ['pork', 'bacon', 'ham', 'sausage', 'prosciutto']
            },
        ]

        # Seed FDA Major 9 allergens
        created_count = 0
        updated_count = 0

        self.stdout.write(self.style.MIGRATE_HEADING('\nSeeding FDA Major 9 Allergens:'))
        for allergen_data in fda_allergens:
            allergen, created = Allergen.objects.get_or_create(
                name=allergen_data['name'],
                defaults={
                    'category': allergen_data['category'],
                    'alternative_names': allergen_data['alternative_names'],
                    'description': allergen_data['description'],
                    'usda_search_terms': allergen_data['usda_search_terms'],
                }
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Created: {allergen.name}')
                )
            else:
                # Update existing allergen with new data
                allergen.category = allergen_data['category']
                allergen.alternative_names = allergen_data['alternative_names']
                allergen.description = allergen_data['description']
                allergen.usda_search_terms = allergen_data['usda_search_terms']
                allergen.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'  ↻ Updated: {allergen.name}')
                )

        # Seed dietary preferences
        self.stdout.write(self.style.MIGRATE_HEADING('\nSeeding Dietary Preferences:'))
        for preference_data in dietary_preferences:
            allergen, created = Allergen.objects.get_or_create(
                name=preference_data['name'],
                defaults={
                    'category': preference_data['category'],
                    'alternative_names': preference_data['alternative_names'],
                    'description': preference_data['description'],
                    'usda_search_terms': preference_data['usda_search_terms'],
                }
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Created: {allergen.name}')
                )
            else:
                # Update existing allergen with new data
                allergen.category = preference_data['category']
                allergen.alternative_names = preference_data['alternative_names']
                allergen.description = preference_data['description']
                allergen.usda_search_terms = preference_data['usda_search_terms']
                allergen.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'  ↻ Updated: {allergen.name}')
                )

        # Summary
        self.stdout.write(self.style.SUCCESS(f'\n✓ Seeding complete!'))
        self.stdout.write(f'  Created: {created_count} allergens')
        self.stdout.write(f'  Updated: {updated_count} allergens')
        self.stdout.write(f'  Total: {Allergen.objects.count()} allergens in database')
