# reviews/admin.py

from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from .models import Review

class ReviewInline(GenericTabularInline):
    """
    Inline genérico para mostrar/editar reseñas
    directamente desde el admin de cualquier modelo reseñable.
    """
    model = Review
    ct_field = 'content_type'
    ct_fk_field = 'object_id'
    extra = 0
    readonly_fields = ('user', 'rating', 'title', 'body', 'created_at', 'updated_at')
    fields = ('user', 'rating', 'title', 'body', 'is_active', 'created_at')
    show_change_link = True


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """
    Configuración del admin para el modelo Review.
    Permite filtrar, buscar y activar/desactivar reseñas.
    """
    list_display = (
        '__str__',
        'content_object',
        'user',
        'rating',
        'is_active',
        'created_at',
    )
    list_filter = (
        'rating',
        'is_active',
        'content_type',
        'created_at',
    )
    search_fields = (
        'title',
        'body',
        'user__username',
        'user__email',
    )
    readonly_fields = ('created_at', 'updated_at')
    actions = ['activate_reviews', 'deactivate_reviews']

    def activate_reviews(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} reseña(s) activada(s).")
    activate_reviews.short_description = "Activar reseñas seleccionadas"

    def deactivate_reviews(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} reseña(s) desactivada(s).")
    deactivate_reviews.short_description = "Desactivar reseñas seleccionadas"
