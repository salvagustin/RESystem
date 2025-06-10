from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from models import Venta, Plantacion

@receiver(post_delete, sender=Venta)
def actualizar_estado_cosecha_al_eliminar(sender, instance, **kwargs):
    print("Venta eliminada - actualizando estado cosecha")
    if instance.cosecha:
        instance.actualizar_estado_cosecha()


@receiver(post_save, sender=Plantacion)
def actualizar_estado_parcela(sender, instance, **kwargs):
    if instance.estado:  # Si está activa
        instance.parcela.estado = False  # Ocupada
    else:
        instance.parcela.estado = True  # Libre
    instance.parcela.save()