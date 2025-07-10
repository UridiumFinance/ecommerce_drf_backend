from django.contrib import admin
from .models import ShippingAddress

@admin.register(ShippingAddress)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'label',        # p.ej. 'Casa', 'Trabajo'
        'street',       # dirección
        'city',
        'region',       # antes 'state_province'
        'postal_code',
        'country',
        'is_default',
        'created_at',
    )
    list_filter   = ('country', 'is_default', 'created_at')
    search_fields = ('user__username', 'label', 'street', 'city', 'postal_code')
    readonly_fields = ('created_at', 'updated_at')