from django.contrib import admin

from .models import Media
from .forms import MediaAdminForm


@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    form = MediaAdminForm
    
    list_display = ["name", "image_preview", "media_type", "key"]
    list_filter = ['media_type']
    search_fields = ['name']
    readonly_fields = ['image_display', 'name', 'size', 'type', 'key']

    fieldsets = (
        ("Subir archivo", {
            'fields': ('file', 's3_path', 'media_type', 'order')
        }),
        ("Vista previa", {
            'fields': ('image_display',)
        }),
        ("Metadatos (auto-llenado)", {
            'fields': ('name', 'size', 'type', 'key')
        }),
    )

    def get_search_results(self, request, queryset, search_term):
        # Limitar solo a imágenes para autocompletado
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        queryset = queryset.filter(media_type='image')
        return queryset, use_distinct