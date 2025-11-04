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
    path('', views.index, name='index'),

    path('profile/<int:pk>/', views.profileDetail, name='profile-detail'),
    path('register/', views.register, name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', custom_logout, name='logout'),
    path('accounts/', include('django.contrib.auth.urls')),

    
    # Recipe URLs
    path('recipe-search/', views.recipeSearch, name='recipe-search'),
    path('recipe/<int:pk>/', views.recipeDetail, name='recipe-detail'),
    path('add-recipe/', views.addRecipe, name='add-recipe'),
    path("ingredient/add/", views.addIngredient, name="add-ingredient"),

    
    # Ingredient and Allergen URLs
    path('ingredient/<int:pk>/', views.ingredientDetail, name='ingredient-detail'),
    path('add-ingredient/', views.addIngredient, name='add-ingredient'),
    path('allergen/<int:pk>/', views.allergenDetail, name='allergen-detail'),
    
    # User-specific URLs
    path('pantry/', views.pantry, name='pantry'),
    path('profile/<int:pk>/', views.profileDetail, name='profile-detail'),

    # AJAX endpoints
    path('api/search-ingredients/', views.search_usda_ingredients, name='search-usda-ingredients'),

    # Admin access URLs
    path("admin/", admin.site.urls),

    # Built-in Django authentication URLs
    path("accounts/", include("django.contrib.auth.urls")),
   
]