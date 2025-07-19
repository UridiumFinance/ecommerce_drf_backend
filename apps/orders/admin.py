from django.contrib import admin

from .models import Order, OrderItem


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display    = (
        'id', 'total', 'status', 'payment_reference', 'created_at'
    )
    search_fields   = ('id', 'payment_reference')
    readonly_fields = ('id',)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display    = (
        'id', 'content_type', 'object_id', 'item_name', 'quantity', 'total_price'
    )
    search_fields   = ('id', 'content_type', 'object_id', 'item_name', 'quantity', 'total_price')
    readonly_fields = ('id',)