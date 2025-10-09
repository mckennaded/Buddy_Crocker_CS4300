#Models.py

#Ingredients Model
class Ingredient(models.Model):
    #Objects
    objects.models.Manager()

    #Ingredient Name
    ingredient_name = models.CharField(max_length=100)

    #Ingredient Count
    ingredient_count = IntegerField()

    #Print out ingredient
    def __str__(self):
        return f'''Name: ({self.ingredient_name})\n
        Count: ({self.ingredient_count})'''


#Pantry Model
class Pantry(models.Model):
    #Objects
    objects.models.Manager()

    #Ingredients in the Pantry
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)