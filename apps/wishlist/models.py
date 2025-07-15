import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from apps.products.models import Size, Weight, Material, Color, Flavor


class Wishlist(models.Model):
    """
    Lista de deseos de un usuario.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wishlist'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Wishlist'
        verbose_name_plural = 'Wishlists'

    def __str__(self):
        return f"Wishlist de {self.user}"  


class WishlistItem(models.Model):
    """
    Un ítem en la lista de deseos.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wishlist = models.ForeignKey(
        Wishlist,
        on_delete=models.CASCADE,
        related_name='items'
    )
    # Generic relation para productos o cursos
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={'model__in': ('product', 'course')},
        null=True,
        blank=True,
    )
    object_id = models.UUIDField(null=True, blank=True)
    item = GenericForeignKey('content_type', 'object_id')

    # Campos opcionales para variantes, igual que en CartItem
    size = models.ForeignKey(Size, on_delete=models.SET_NULL, null=True, blank=True)
    weight = models.ForeignKey(Weight, on_delete=models.SET_NULL, null=True, blank=True)
    material = models.ForeignKey(Material, on_delete=models.SET_NULL, null=True, blank=True)
    color = models.ForeignKey(Color, on_delete=models.SET_NULL, null=True, blank=True)
    flavor = models.ForeignKey(Flavor, on_delete=models.SET_NULL, null=True, blank=True)

    added_at = models.DateTimeField(default=timezone.now, editable=False, db_index=True)

    class Meta:
        unique_together = [
            (
                'wishlist', 'content_type', 'object_id',
                'size', 'weight', 'material', 'color', 'flavor'
            ),
        ]
        indexes = [models.Index(fields=['content_type', 'object_id'])]
        verbose_name = 'Wishlist Item'
        verbose_name_plural = 'Wishlist Items'

    def __str__(self):
        return f"{self.item} en wishlist de {self.wishlist.user}"
