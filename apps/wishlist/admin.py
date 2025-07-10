from django.contrib import admin
from .models import Wishlist, WishlistItem


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'created_at',
        'item_count',
    )
    readonly_fields = ('id', 'created_at')
    search_fields = ('user',)
    ordering = ('-created_at',)

    def item_count(self, obj):
        return obj.items.count()
    item_count.short_description = 'Num. de ítems'


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'wishlist',
        'item',
        'size',
        'weight',
        'material',
        'color',
        'flavor',
        'added_at',
    )
    list_filter = (
        'content_type',
        'added_at',
    )
    search_fields = (
        'object_id',
    )
    list_select_related = (
        'wishlist',
        'content_type',
        'size', 'weight', 'material', 'color', 'flavor',
    )
    readonly_fields = (
        'id',
        'added_at',
    )
    ordering = ('-added_at',)
