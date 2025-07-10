from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Wishlist
from apps.authentication.models import UserAccount


@receiver(post_save, sender=UserAccount)
def create_wishlist(sender, instance, created, **kwargs):
    """
    Crea una instancia de carrito para un usuario
    """
    if created:
        # Solo crea si es un nuevo usuario
        Wishlist.objects.create(user=instance)