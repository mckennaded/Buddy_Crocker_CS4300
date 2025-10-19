# Buddy_Crocker_CS4300


# Run all tests
python manage.py test

# Run specific test file
python manage.py test Buddy_Crocker.tests.test_models
python manage.py test Buddy_Crocker.tests.test_views
python manage.py test Buddy_Crocker.tests.test_urls

# Run specific test class
python manage.py test Buddy_Crocker.tests.test_models.RecipeModelTest

# Run with verbose output
python manage.py test --verbosity=2
