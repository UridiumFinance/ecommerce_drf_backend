from django.apps import AppConfig


class AddressesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.addresses'

    def ready(self):
        import apps.addresses.signals