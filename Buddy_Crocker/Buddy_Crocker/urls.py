"""
URL configuration for Buddy Crocker app.

Defines URL patterns that map URLs to view functions.
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views
from .views import CustomLoginView
from .views import custom_logout


urlpatterns = [
    # Home page
    path('', views.index, name='index'),

    #User Auth URLs    
    path('register/', views.register, name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', custom_logout, name='logout'),
    path('accounts/', include('django.contrib.auth.urls')),

    # Profile URLs
    path('profile/<int:pk>/', views.profileDetail, name='profile-detail'),

    # Recipe URLs
    path('recipe-search/', views.recipeSearch, name='recipe-search'),
    path('recipe/<int:pk>/', views.recipeDetail, name='recipe-detail'),
    #path('add-recipe/', views.addRecipe, name='add-recipe'),
    path("add-recipe/<path:prefill>", views.add_recipe_prefill, name="add-recipe-prefill"),
    path('add-recipe/', views.addRecipe, name='add-recipe'),
    
    #path("add-ingredients/", views.add_ingredients_view, name="add-ingredients"),
    
    # Ingredient and Allergen URLs
    path('ingredient/<int:pk>/', views.ingredientDetail, name='ingredient-detail'),
    path('add-ingredient/', views.addIngredient, name='add-ingredient'),
    path('allergen/<int:pk>/', views.allergenDetail, name='allergen-detail'),
    
    # User-specific URLs
    path('pantry/', views.pantry, name='pantry'),   

    # AJAX endpoints
    path('api/search-ingredients/', views.search_usda_ingredients, name='search-usda-ingredients'),

    # Admin access URLs
    path("admin/", admin.site.urls),
    path("404/", views.preview_404, name="404"),
    path("500/", views.preview_500, name="500"), 
    
]

handler404 = "Buddy_Crocker.views.page_not_found_view"
handler500 = "Buddy_Crocker.views.server_error_view"



