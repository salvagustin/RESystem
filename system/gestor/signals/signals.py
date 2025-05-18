from django.db.models.signals import post_delete
from django.dispatch import receiver
from models import Venta

@receiver(post_delete, sender=Venta)
def actualizar_estado_cosecha_al_eliminar(sender, instance, **kwargs):
    print("Venta eliminada - actualizando estado cosecha")
    if instance.cosecha:
        instance.actualizar_estado_cosecha()
