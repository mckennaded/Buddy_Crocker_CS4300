from django.shortcuts import render

def index(request):
    return render(request, 'index.html')

def pantry(request):
    return render(request, 'pantry.html')

def recipeSearch(request):
    return render(request, 'recipe-search.html')

def addRecipe(request):
    return render(request, 'add-recipe.html')