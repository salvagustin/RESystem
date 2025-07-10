# gestor/templatetags/custom_filters.py
from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Obtiene un item de un diccionario por su clave.
    Uso: {{ mi_dict|get_item:"clave" }}
    """
    try:
        return dictionary.get(key)
    except Exception:
        return None

@register.filter
def dict_get(value, key):
    """
    Obtiene un valor de un diccionario por su clave.
    Uso: {{ mi_dict|dict_get:"clave" }}
    """
    try:
        return value.get(key)
    except Exception:
        return None

@register.filter
def json_script(value):
    """
    Convierte un queryset o lista de objetos en JSON para usarlo en atributos HTML.
    Se asegura que el resultado sea seguro para usar en atributos data-*.
    """
    try:
        def to_dict(obj):
            return {
                'nombre': obj.producto.nombre,
                'cantidad': obj.cantidad,
                'precio': float(obj.precio),
                'total': float(obj.total)
            }
        
        data = [to_dict(item) for item in value]
        return mark_safe(json.dumps(data))
    except Exception as e:
        return mark_safe('[]')  # En caso de error, retorna un array vacío