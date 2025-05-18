from django.apps import AppConfig

class VentasConfig(AppConfig):
    name = 'ventas'

    def ready(self):
        import signals.signals

class GestorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gestor'
