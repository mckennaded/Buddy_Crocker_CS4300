from django import template

register = template.Library()

@register.filter
def intersect(list1, list2):
    """Check if two lists have any common elements."""
    return any(item in list2 for item in list1)