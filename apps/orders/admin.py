from django.contrib import admin
from .models import Order, OrderItem

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # Columnas que mostramos en la lista
    list_display = (
        'id',
        'user',
        'status',
        'tracking_number',
        'total',
        'created_at',
    )
    # Editable en la lista: solo status y tracking_number
    list_editable = (
        'status',
        'tracking_number',
    )
    # Filtros rápidos
    list_filter = (
        'status',
        'created_at',
    )
    search_fields = (
        'id',
        'payment_reference',
        'tracking_number',
        'user__username',
        'user__email',
    )
    ordering = ('-created_at',)

    # Sólo estos campos aparecerán en el form de detalle de la orden
    fields = (
        'id',
        'user',
        'total',
        'payment_reference',
        'status',
        'tracking_number',
        'tracking_url',
        'created_at',
    )
    # De esos, solo los marcados aquí son de solo lectura
    readonly_fields = (
        'id',
        'user',
        'total',
        'payment_reference',
        'created_at',
    )

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'order',
        'item_name',
        'quantity',
        'unit_price',
        'item_discount',
        'total_price',
    )
    search_fields = (
        'id',
        'item_name',
        'object_id',
    )
    list_filter = (
        'order__status',
    )
    readonly_fields = ('id',)
