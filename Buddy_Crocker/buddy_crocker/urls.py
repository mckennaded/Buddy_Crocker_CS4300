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

    #User Auth URLs
    path('register/', views.register, name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', custom_logout, name='logout'),
    path('accounts/', include('django.contrib.auth.urls')),

    # Profile URLs
    path('profile/<int:pk>/', views.profile_detail, name='profile-detail'),

    # Recipe URLs
    path('recipe-search/', views.recipeSearch, name='recipe-search'),
    path('recipe/<int:pk>/', views.recipeDetail, name='recipe-detail'),
    path('add-recipe/', views.addRecipe, name='add-recipe'),
    path('edit-recipe/<int:pk>', views.editRecipe, name='edit-recipe'),
    path('delete-recipe/<int:pk>/', views.deleteRecipe, name='delete-recipe'),
    path('recipe/<int:pk>/quick-add-ingredients/', views.quick_add_ingredients, name='quick-add-ingredients'),
    
    #path("add-ingredients/", views.add_ingredients_view, name="add-ingredients"),

    # Ingredient and Allergen URLs
    path('ingredient/<int:pk>/', views.ingredientDetail, name='ingredient-detail'),
    path('add-ingredient/', views.addIngredient, name='add-ingredient'),
    path('edit-ingredient/<int:pk>/', views.editIngredient, name='edit-ingredient'),
    path('delete-ingredient/<int:pk>/', views.deleteIngredient, name='delete-ingredient'),
    path('allergen/<int:pk>/', views.allergenDetail, name='allergen-detail'),
    
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

handler404 = "buddy_crocker.views.page_not_found_view"
handler500 = "buddy_crocker.views.server_error_view"
