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

# pylint: disable=line-too-long

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
    path('edit-recipe/<int:pk>', views.edit_recipe, name='edit-recipe'),
    path('delete-recipe/<int:pk>/', views.delete_recipe, name='delete-recipe'),
    path(
        'recipe/<int:pk>/quick-add-ingredients/',
        views.quick_add_ingredients,
        name='quick-add-ingredients',
    ),
    path(
        'api/quick-add-usda-ingredient/',
        views.quick_add_usda_ingredient,
        name='quick-add-usda-ingredient',
    ),

    # AI recipe generator
    path(
        'ai-recipes/',
        views.ai_recipe_generator,
        name='ai-recipe-generator',
    ),

    # Ingredient and Allergen URLs
    path('ingredient/<int:pk>/', views.ingredient_detail, name='ingredient-detail'),
    path('add-ingredient/', views.add_ingredient, name='add-ingredient'),
    path('edit-ingredient/<int:pk>/', views.edit_ingredient, name='edit-ingredient'),
    path('delete-ingredient/<int:pk>/', views.delete_ingredient, name='delete-ingredient'),
    path('allergen/<int:pk>/', views.allergen_detail, name='allergen-detail'),

    # User-specific URLs
    path('pantry/', views.pantry, name='pantry'),

    # Pantry scanning endpoints
    path('api/pantry/scan/', views.scan_pantry, name='scan-pantry'),
    path('api/pantry/add-scanned/', views.add_scanned_ingredients, name='add-scanned-ingredients'),

    # AJAX endpoints
    path(
        'api/search-ingredients/',
        views.search_usda_ingredients,
        name='search-usda-ingredients',
    ),
    path(
        'api/ingredient/<int:pk>/add-custom-portion/',
        views.add_custom_portion,
        name='add-custom-portion',
    ),

    # Admin access URLs
    path("admin/", admin.site.urls),

    # Error preview routes (accept extra path segments)
    path("404/", views.preview_404, name="preview-404"),
    path("404/<path:any>", views.preview_404, name="preview-404-any"),

    # exact
    path("500/", views.preview_500, name="preview-500"),
    path("500/<path:any>", views.preview_500, name="preview-500-any"),

    # Shopping List URLs
    path('shopping-list/', views.shopping_list_view, name='shopping-list'),
]

# Django error handlers - must be lowercase variable names
handler404 = "buddy_crocker.views.page_not_found_view"
handler500 = "buddy_crocker.views.server_error_view"
