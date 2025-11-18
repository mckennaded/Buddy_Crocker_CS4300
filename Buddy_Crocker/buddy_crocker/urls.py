"""
URL configuration for Buddy Crocker app.

Defines URL patterns that map URLs to view functions.
"""
from django.contrib import admin
from django.urls import path, include
# from django.contrib.auth import views as auth_views
from . import views
from .views import CustomLoginView
from .views import custom_logout


urlpatterns = [
    # Home page
    path('', views.index, name='index'),

    # User Auth URLs
    path('register/', views.register, name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', custom_logout, name='logout'),
    path('accounts/', include('django.contrib.auth.urls')),

    # Profile URLs
    path('profile/<int:pk>/', views.profile_detail, name='profile-detail'),

    # Recipe URLs
    path('recipe-search/', views.recipe_search, name='recipe-search'),
    path('recipe/<int:pk>/', views.recipe_detail, name='recipe-detail'),
    path('add-recipe/', views.add_recipe, name='add-recipe'),

    # path("add-ingredients/", views.add_ingredients_view, name="add-ingredients"),

    # AI Recipe Generator
    path("recipe_generator/", views.recipe_generator, name="recipe-generator"),

    # Ingredient and Allergen URLs
    path('ingredient/<int:pk>/', views.ingredient_detail, name='ingredient-detail'),
    path('add-ingredient/', views.add_ingredient, name='add-ingredient'),
    path('allergen/<int:pk>/', views.allergen_detail, name='allergen-detail'),

    # User-specific URLs
    path('pantry/', views.pantry, name='pantry'),

    # AJAX endpoints
    path('api/search-ingredients/', views.search_usda_ingredients, name='search-usda-ingredients'),

    # Admin access URLs
    path("admin/", admin.site.urls),

    # Error preview routes (accept extra path segments)
    path("404/", views.preview_404, name="preview-404"),
    path("404/<path:any>", views.preview_404, name="preview-404-any"),

    # exact
    path("500/", views.preview_500, name="preview-500"),
    path("500/<path:any>", views.preview_500, name="preview-500-any"),
]

# Django error handlers - these are module-level variables, not constants
# pylint: disable=invalid-name
handler404 = "buddy_crocker.views.page_not_found_view"
handler500 = "buddy_crocker.views.server_error_view"
