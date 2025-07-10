from django.contrib import admin

from .models import (
    Cart, CartItem, Coupon, CouponRedemption,
    ShippingProvider, ShippingZone, ShippingMethod
)


# --- Cart & CartItem ---
class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = (
        'item', 'size', 'color', 'count',
        'unit_price', 'discount_amount', 'total_price',
        'coupon', 'added_at', 'updated_at',
    )
    fields = (
        'item', 'size', 'color', 'count',
        'unit_price', 'discount_amount', 'total_price',
        'coupon', 'added_at', 'updated_at',
    )
    can_delete = False

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display    = ('id', 'user', 'created_at', 'total_items', 'subtotal', 'items_discount', 'cart_discount', 'shipping_cost', 'total')
    list_filter     = ('created_at', 'user')
    search_fields   = ('id', 'user')
    readonly_fields = ('created_at', 'subtotal', 'items_discount', 'cart_discount', 'shipping_cost', 'total')
    inlines         = [CartItemInline]

    def total_items(self, obj):
        return obj.items.count()
    total_items.short_description = 'Número de ítems'

    def subtotal(self, obj):
        return obj.subtotal()
    subtotal.short_description = 'Subtotal'

    def items_discount(self, obj):
        return obj.items_discount()
    items_discount.short_description = 'Descuento ítems'

    def cart_discount(self, obj):
        amount, free = obj.cart_discount()
        return f"{amount}{' (envío gratis)' if free else ''}"
    cart_discount.short_description = 'Descuento carrito'

    def total(self, obj):
        return obj.total()
    total.short_description = 'Total'


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display    = (
        'id', 'cart', 'item', 'count',
        'unit_price', 'discount_amount', 'total_price', 'coupon', 'added_at'
    )
    list_filter     = ('content_type', 'added_at')
    search_fields   = ('id', 'cart__id', 'object_id', 'coupon__code')
    readonly_fields = (
        'cart', 'item', 'content_type', 'object_id',
        'size', 'weight', 'material', 'color', 'flavor',
        'count', 'unit_price', 'discount_amount', 'total_price',
        'coupon', 'added_at', 'updated_at'
    )


# --- Coupons & Redemptions ---
class CouponRedemptionInline(admin.TabularInline):
    model = CouponRedemption
    extra = 0
    readonly_fields = ('user', 'order', 'redeemed_at')
    fields = ('user', 'order', 'redeemed_at')
    can_delete = False

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display    = (
        'code', 'coupon_type', 'discount_value',
        'valid_from', 'valid_to', 'active', 'per_user_limit', 'uses_count'
    )
    list_filter     = ('coupon_type', 'active', 'valid_from', 'valid_to')
    search_fields   = ('code',)
    readonly_fields = ('uses_count',)
    inlines         = [CouponRedemptionInline]


# --- Shipping ---
class ShippingMethodInline(admin.TabularInline):
    model = ShippingMethod
    extra = 0
    fields = (
        'name', 'code', 'base_rate', 'per_kg_rate',
        'min_delivery_days', 'max_delivery_days', 'active'
    )

@admin.register(ShippingProvider)
class ShippingProviderAdmin(admin.ModelAdmin):
    list_display    = ('name', 'code', 'active')
    list_filter     = ('active',)
    search_fields   = ('name', 'code')
    inlines         = [ShippingMethodInline]

@admin.register(ShippingZone)
class ShippingZoneAdmin(admin.ModelAdmin):
    list_display    = ('name',)
    search_fields   = ('name',)

@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    list_display    = (
        'name', 'code', 'provider', 'zone',
        'base_rate', 'per_kg_rate',
        'min_delivery_days', 'max_delivery_days', 'active'
    )
    list_filter     = ('provider', 'zone', 'active')
    search_fields   = ('name', 'code', 'provider__name', 'zone__name')
    raw_id_fields   = ('provider', 'zone')
    readonly_fields = ('id',)