from rest_framework import serializers
from .models import Order, OrderItem
from apps.addresses.serializers import ShippingAddressSerializer
from apps.cart.serializers import ShippingMethodSerializer, CouponSerializer
from apps.products.serializers import (
    ProductSerializer,
)
from apps.authentication.serializers import UserPublicSerializer

ITEM_SERIALIZERS = {
    'product': ProductSerializer,
    # 'course': CourseSerializer,
}

class PolymorphicRelatedField(serializers.RelatedField):
    def to_representation(self, value):
        model_name = value._meta.model_name
        serializer_cls = ITEM_SERIALIZERS.get(model_name)
        if not serializer_cls:
            raise Exception(f"No hay serializer para {model_name}")
        return serializer_cls(value, context=self.context).data
    
class OrderItemSerializer(serializers.ModelSerializer):
    """
    Serializer para cada línea de pedido. 
    Incluye los datos “congelados” de nombre, precio y variantes.
    """
    item                   = PolymorphicRelatedField(read_only=True)
    class Meta:
        model = OrderItem
        fields = [
            'id',
            'content_type',
            'object_id',
            'item_name',
            'item',
            'unit_price',
            'quantity',
            'item_discount',
            'total_price',
            'size_title',
            'weight_title',
            'material_title',
            'color_title',
            'flavor_title',
        ]


class OrderSerializer(serializers.ModelSerializer):
    """
    Serializer principal de Order, con los campos financieros y
    la lista anidada de OrderItem.
    """
    user               = UserPublicSerializer(read_only=True)
    shipping_address   = ShippingAddressSerializer(read_only=True)
    shipping_method    = ShippingMethodSerializer(read_only=True)
    coupon             = CouponSerializer(read_only=True, allow_null=True)
    items              = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'user',
            'shipping_address',
            'shipping_method',
            'shipping_cost',
            'coupon',
            'subtotal',
            'items_discount',
            'global_discount',
            'tax_amount',
            'total',
            'status',
            'payment_reference',
            'created_at',
            'updated_at',
            'items',
        ]
        read_only_fields = fields