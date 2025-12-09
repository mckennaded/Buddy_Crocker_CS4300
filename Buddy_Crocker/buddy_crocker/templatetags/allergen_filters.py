"""
Custom Django template filters for list operations.

Filters:
    intersect: Checks if two lists share any common elements.

Usage:
    Load this filter in templates with:
        {% load custom_filters %}

    Then use in templates:
        {% if user.allergens|intersect:ingredient.allergens %}
            <span class="warning">Contains allergens!</span>
        {% endif %}
"""

from django import template

register = template.Library()

@register.filter
def intersect(list1, list2):
    """Check if two lists have any common elements."""
    return any(item in list2 for item in list1)
