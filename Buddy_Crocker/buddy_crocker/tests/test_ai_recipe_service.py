{% extends "buddy_crocker/base.html" %}
{% block content %}
<div class="container mt-4">
  <h1 class="mb-4">Buddy Crocker's Recipe Generator</h1>

  <!-- Loading Animation -->
  <div id="loadingOverlay" class="loading-overlay" style="display: none;">
    <div class="cooking-pan-loader">
      <div class="pan">
        <div class="pan-body">
          <div class="steam">
            <div class="steam-bubble"></div>
            <div class="steam-bubble"></div>
            <div class="steam-bubble"></div>
            <div class="steam-bubble"></div>
          </div>
          <div class="flame">
            <div class="flame-inner"></div>
          </div>
        </div>
        <div class="handle"></div>
      </div>
      <div class="loading-text">
        <div class="cooking-text">Cooking up recipes...</div>
        <div class="progress-bar">
          <div class="progress-fill"></div>
        </div>
        <div class="time-left">Generating magic ✨</div>
      </div>
    </div>
  </div>

  <!-- Error Messages -->
  {% if error_msg %}
    <div class="alert alert-danger alert-dismissible fade show" role="alert">
      <strong>Error:</strong> {{ error_msg }}
    </div>
  {% endif %}

  <!-- Success/Info Messages -->
  {% if messages %}
    {% for message in messages %}
      <div class="alert alert-{{ message.tags }} alert-dismissible fade show" role="alert">
        {{ message }}
        {% if 'saved to your profile' in message|lower %}
          <a href="{% url 'profile-detail' user.pk %}" class="alert-link">View Profile</a>
        {% endif %}
      </div>
    {% endfor %}
  {% endif %}

  <!-- Ingredient Selection -->
  <div class="card mb-4">
    <div class="card-header bg-primary text-white">
      <h5 class="mb-0">Select Ingredients from Your Pantry</h5>
    </div>
    <div class="card-body">
      {% if pantry_ingredients %}
        <form method="post" action="{% url 'ai-recipe-generator' %}" id="recipeForm">
          {% csrf_token %}
          <div class="row">
            {% for ingredient in pantry_ingredients %}
              <div class="col-md-6 col-lg-4 mb-2">
                <div class="form-check">
                  <input class="form-check-input" 
                         type="checkbox" 
                         name="selected_ingredients" 
                         value="{{ ingredient.id }}"
                         id="ing_{{ ingredient.id }}">
                  <label class="form-check-label" for="ing_{{ ingredient.id }}">
                    {{ ingredient.name }}
                  </label>
                </div>
              </div>
            {% endfor %}
          </div>
          <div class="mt-3 d-flex gap-2">
            <button type="submit" name="generate_recipes" class="btn btn-primary btn-lg generate-btn">
              <span class="btn-text">Generate Recipes</span>
              <span class="spinner-border spinner-border-sm d-none" role="status"></span>
            </button>
            <a href="{% url 'shopping-list' %}" class="btn btn-outline-success btn-lg">
              <i class="bi bi-cart"></i> View Shopping List
            </a>
          </div>
        </form>
      {% else %}
        <div class="alert alert-info mb-0">
          Your pantry is empty. <a href="{% url 'pantry' %}">Add ingredients</a> to start!
        </div>
      {% endif %}
    </div>
  </div>

  <!-- Generated Recipes -->
  {% if zipped_recipes_forms %}
    <div class="row">
      <div class="col-12">
        <h2 class="mb-4">Generated Recipes ({{ zipped_recipes_forms|length }})</h2>
      </div>
      {% for recipe, form in zipped_recipes_forms %}
        <div class="col-12 mb-4">
          <div class="card shadow-sm">
            <div class="card-header {% if recipe.uses_only_pantry %}bg-success{% else %}bg-info{% endif %} text-white">
              <h4 class="mb-0">{{ recipe.title }}</h4>
              <small>
                {% if recipe.uses_only_pantry %}
                  Uses Only Pantry
                {% else %}
                  Includes Extras
                {% endif %}
              </small>
            </div>
            <div class="card-body">
              <h5 class="mb-3">Ingredients:</h5>
              <form method="post" action="{% url 'ai-recipe-generator' %}">
                {% csrf_token %}
                <div class="row">
                  {% for ing in recipe.ingredients %}
                    <div class="col-md-6 mb-2">
                      <div class="form-check">
                        <input class="form-check-input" 
                               type="checkbox" 
                               name="shopping_{{ forloop.parentloop.counter }}_{{ forloop.counter }}"
                               value="{{ ing }}" 
                               id="shop_{{ forloop.parentloop.counter }}_{{ forloop.counter }}">
                        <label class="form-check-label" for="shop_{{ forloop.parentloop.counter }}_{{ forloop.counter }}">
                          {{ ing }}
                        </label>
                      </div>
                    </div>
                  {% endfor %}
                </div>

                <div class="d-flex gap-2 mt-3">
                  <button type="submit" 
                          name="save_recipe_{{ forloop.counter }}" 
                          class="btn btn-success">
                    Save Recipe
                  </button>
                  <button type="submit" 
                          name="add_to_shopping_{{ forloop.counter }}" 
                          class="btn btn-outline-warning">
                    Add to Shopping List
                  </button>
                  <a href="{% url 'profile-detail' user.pk %}" class="btn btn-outline-primary">
                    View Profile
                  </a>
                </div>
              </form>

              <hr>
              <h5 class="mb-3">Instructions:</h5>
              <div style="background-color: #f8f9fa; padding: 1rem; border-radius: 0.25rem; border-left: 4px solid #0d6efd;">
                {{ recipe.instructions|linebreaks }}
              </div>
            </div>
          </div>
        </div>
      {% endfor %}
    </div>
  {% endif %}
</div>

<style>
/* Cooking Pan Loading Animation */
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
}

.cooking-pan-loader {
  text-align: center;
  max-width: 400px;
  padding: 40px;
  background: white;
  border-radius: 20px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.2);
  border: 4px solid #0B63F2;
}

.pan {
  position: relative;
  width: 120px;
  height: 80px;
  margin: 0 auto 30px;
  animation: panBounce 2s infinite;
}

.pan-body {
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100px;
  height: 60px;
  background: linear-gradient(145deg, #c0c0c0, #a0a0a0);
  border-radius: 50px 50px 10px 10px;
  border: 3px solid #8a8a8a;
  box-shadow: 
    0 8px 16px rgba(0,0,0,0.3),
    inset 0 2px 4px rgba(255,255,255,0.3);
}

.steam {
  position: absolute;
  top: -20px;
  left: 50%;
  transform: translateX(-50%);
  width: 40px;
  height: 40px;
}

.steam-bubble {
  position: absolute;
  background: rgba(255,255,255,0.8);
  border-radius: 50%;
  animation: steamRise 2s infinite;
}

.steam-bubble:nth-child(1) { width: 8px; height: 8px; left: 10px; animation-delay: 0s; }
.steam-bubble:nth-child(2) { width: 12px; height: 12px; left: 50%; animation-delay: 0.3s; }
.steam-bubble:nth-child(3) { width: 10px; height: 10px; right: 10px; animation-delay: 0.6s; }
.steam-bubble:nth-child(4) { width: 6px; height: 6px; left: 30px; animation-delay: 0.9s; }

.flame {
  position: absolute;
  bottom: -15px;
  left: 50%;
  transform: translateX(-50%);
  width: 30px;
  height: 25px;
}

.flame-inner {
  width: 100%;
  height: 100%;
  background: linear-gradient(45deg, #ff6b35, #f7931e, #ffcc02);
  border-radius: 50% 50% 50% 50% / 60% 60% 40% 40%;
  animation: flameFlicker 0.5s infinite alternate;
  box-shadow: 0 0 10px #ff6b35;
}

.handle {
  position: absolute;
  right: -30px;
  top: 20px;
  width: 40px;
  height: 8px;
  background: linear-gradient(145deg, #d0d0d0, #b0b0b0);
  border-radius: 4px;
  transform-origin: left center;
  transform: rotate(-15deg);
}

.cooking-text {
  font-size: 1.8rem;
  font-weight: bold;
  color: #0B63F2;
  margin-bottom: 20px;
  font-family: 'Oswald', sans-serif;
}

.progress-bar {
  width: 250px;
  height: 20px;
  background: #e9ecef;
  border-radius: 10px;
  margin: 0 auto 15px;
  overflow: hidden;
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #0B63F2, #28a745);
  border-radius: 10px;
  width: 0%;
  animation: progressFill 3s infinite;
  box-shadow: 0 0 10px rgba(11,99,242,0.5);
}

.time-left {
  color: #6c757d;
  font-size: 1.1rem;
  font-style: italic;
}

/* Button Loading State */
.generate-btn:disabled {
  opacity: 0.7;
}

@keyframes panBounce {
  0%, 100% { transform: translateY(0px); }
  50% { transform: translateY(-5px); }
}

@keyframes steamRise {
  0% { 
    transform: translateY(0) scale(1);
    opacity: 1;
  }
  100% { 
    transform: translateY(-30px) scale(0.5);
    opacity: 0;
  }
}

@keyframes flameFlicker {
  0% { transform: scale(1) rotate(-2deg); }
  100% { transform: scale(1.1) rotate(2deg); }
}

@keyframes progressFill {
  0% { width: 0%; }
  50% { width: 70%; }
  100% { width: 100%; }
}
</style>

<script>
document.addEventListener('DOMContentLoaded', function() {
  const form = document.getElementById('recipeForm');
  const generateBtn = document.querySelector('.generate-btn');
  const loadingOverlay = document.getElementById('loadingOverlay');
  
  if (form) {
    form.addEventListener('submit', function(e) {
      const generateRecipesBtn = e.submitter && e.submitter.name === 'generate_recipes';
      if (generateRecipesBtn) {
        e.preventDefault();
        
        // Show loading
        loadingOverlay.style.display = 'flex';
        generateBtn.disabled = true;
        generateBtn.querySelector('.btn-text').classList.add('d-none');
        generateBtn.querySelector('.spinner-border').classList.remove('d-none');
        
        // Submit form after short delay
        setTimeout(() => {
          form.submit();
        }, 500);
      }
    });
  }
});
</script>
{% endblock %}
