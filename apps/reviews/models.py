from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation

class Review(models.Model):
    """
    Una reseña genérica: puede apuntar a cualquier modelo registrado
    como reseñable mediante ContentType/Object ID.
    """
    # --- Campos de relación genérica ---
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="Tipo de modelo reseñable (Product, Course, etc.)"
    )
    object_id = models.UUIDField()
    content_object = GenericForeignKey('content_type', 'object_id')

    # --- Quién y cuándo ---
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
        help_text="Usuario que dejó la reseña"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --- Datos de la reseña ---
    RATING_CHOICES = [(i, f"{i} estrella{'s' if i>1 else ''}") for i in range(1, 6)]
    rating = models.PositiveSmallIntegerField(
        choices=RATING_CHOICES,
        help_text="Calificación de 1 a 5"
    )
    title = models.CharField(
        max_length=200,
        help_text="Título breve de la reseña",
    )
    body = models.TextField(
        help_text="Texto completo de la reseña",
        blank=True,
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Si la reseña está visible públicamente"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Reseña"
        verbose_name_plural = "Reseñas"

    def __str__(self):
        return f"{self.user} • {self.rating}★ • {self.title}"


# -----------------------------------------------------
# Para que cualquier modelo “reseñable” tenga acceso rápido:
# -----------------------------------------------------
class Reviewable(models.Model):
    """
    Mix-in abstracto. Agrega un GenericRelation para acceder
    a todas las reseñas asociadas.
    """
    reviews = GenericRelation(
        Review,
        content_type_field='content_type',
        object_id_field='object_id',
        related_query_name='reviews'
    )

    class Meta:
        abstract = True