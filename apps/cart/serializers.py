from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from rest_framework.exceptions import ValidationError

from .models import (
    Cart,
    CartItem,
    Coupon,
    ShippingProvider,
    ShippingZone,
    ShippingMethod,
)
from apps.products.serializers import (
    ProductSerializer,
    SizeSerializer,
    WeightSerializer,
    MaterialSerializer,
    ColorSerializer,
    FlavorSerializer,
)
from apps.products.models import Size, Weight, Material, Color, Flavor
from apps.addresses.serializers import ShippingAddressSerializer
from apps.addresses.models import ShippingAddress

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


class ShippingProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingProvider
        fields = ['id', 'name', 'code']


class ShippingZoneSerializer(serializers.ModelSerializer):
    # Sobrescribimos 'countries' para devolver una lista de códigos ISO
    countries = serializers.SerializerMethodField()

    class Meta:
        model = ShippingZone
        fields = ['id', 'name', 'countries']

    def get_countries(self, zone):
        # zone.countries puede ser un iterable de Country objects
        # str(country) devuelve el código ISO (p.e. 'PE')
        return [str(country) for country in zone.countries]


class ShippingMethodSerializer(serializers.ModelSerializer):
    provider     = ShippingProviderSerializer(read_only=True)
    zone         = ShippingZoneSerializer(read_only=True)
    cost_for_1kg = serializers.SerializerMethodField()

    class Meta:
        model = ShippingMethod
        fields = [
            'id',
            'provider',
            'zone',
            'name',
            'code',
            'base_rate',
            'per_kg_rate',
            'min_delivery_days',
            'max_delivery_days',
            'cost_for_1kg',
        ]

    def get_cost_for_1kg(self, obj):
        return obj.calculate_cost(total_weight_kg=Decimal('1.0'))


class CartItemSerializer(serializers.ModelSerializer):
    # Lectura
    item                   = PolymorphicRelatedField(read_only=True)
    size                   = serializers.SerializerMethodField()
    weight                 = serializers.SerializerMethodField()
    material               = serializers.SerializerMethodField()
    color                  = serializers.SerializerMethodField()
    flavor                 = serializers.SerializerMethodField()
    added_at               = serializers.DateTimeField(read_only=True)
    updated_at             = serializers.DateTimeField(read_only=True)
    time_in_cart           = serializers.SerializerMethodField()
    original_unit_price    = serializers.SerializerMethodField()
    item_discount_amount   = serializers.SerializerMethodField()
    final_unit_price       = serializers.SerializerMethodField()
    total_before_discount  = serializers.SerializerMethodField()
    total_after_discount   = serializers.SerializerMethodField()

    # Escritura variantes y cupón por ítem
    content_type = serializers.SlugRelatedField(
        slug_field='model',
        queryset=ContentType.objects.filter(model__in=('product','course')),
        write_only=True
    )
    object_id   = serializers.UUIDField(write_only=True)
    size_id     = serializers.PrimaryKeyRelatedField(
        queryset=Size.objects.all(), source='size',
        write_only=True, allow_null=True, required=False
    )
    weight_id   = serializers.PrimaryKeyRelatedField(
        queryset=Weight.objects.all(), source='weight',
        write_only=True, allow_null=True, required=False
    )
    material_id = serializers.PrimaryKeyRelatedField(
        queryset=Material.objects.all(), source='material',
        write_only=True, allow_null=True, required=False
    )
    color_id    = serializers.PrimaryKeyRelatedField(
        queryset=Color.objects.all(), source='color',
        write_only=True, allow_null=True, required=False
    )
    flavor_id   = serializers.PrimaryKeyRelatedField(
        queryset=Flavor.objects.all(), source='flavor',
        write_only=True, allow_null=True, required=False
    )
    count       = serializers.IntegerField(min_value=1)
    coupon_code = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = CartItem
        fields = (
            'id', 'item',
            'size', 'weight', 'material', 'color', 'flavor',
            'added_at', 'updated_at', 'time_in_cart',
            'original_unit_price', 'item_discount_amount',
            'final_unit_price', 'total_before_discount', 'total_after_discount',
            'content_type', 'object_id',
            'size_id', 'weight_id', 'material_id', 'color_id', 'flavor_id',
            'count', 'coupon_code',
        )
        read_only_fields = (
            'item', 'size', 'weight', 'material', 'color', 'flavor',
            'added_at', 'updated_at', 'time_in_cart',
            'original_unit_price', 'item_discount_amount',
            'final_unit_price', 'total_before_discount', 'total_after_discount',
        )

    def validate(self, data):
        ct = data.get('content_type') or getattr(self.instance, 'content_type', None)
        if ct and ct.model != 'product':
            for fld in ('size_id','weight_id','material_id','color_id','flavor_id'):
                if self.initial_data.get(fld):
                    raise ValidationError("Sólo productos pueden llevar atributos de variante.")
        return data

    def get_size(self, obj):
        return SizeSerializer(obj.size).data if obj.size else None

    def get_weight(self, obj):
        return WeightSerializer(obj.weight).data if obj.weight else None

    def get_material(self, obj):
        return MaterialSerializer(obj.material).data if obj.material else None

    def get_color(self, obj):
        return ColorSerializer(obj.color).data if obj.color else None

    def get_flavor(self, obj):
        return FlavorSerializer(obj.flavor).data if obj.flavor else None

    def get_time_in_cart(self, obj):
        return (timezone.now() - obj.added_at).total_seconds()

    def get_original_unit_price(self, obj):
        return obj.unit_price()

    def get_item_discount_amount(self, obj):
        return obj.discount_amount.quantize(Decimal('0.01'))

    def get_final_unit_price(self, obj):
        if obj.count:
            net = (obj.unit_price() * obj.count - obj.discount_amount) / obj.count
        else:
            net = obj.unit_price()
        return net.quantize(Decimal('0.01'))

    def get_total_before_discount(self, obj):
        return (obj.unit_price() * obj.count).quantize(Decimal('0.01'))

    def get_total_after_discount(self, obj):
        return (self.get_final_unit_price(obj) * obj.count).quantize(Decimal('0.01'))

    def create(self, validated_data):
        cart      = self.context['cart']
        ct        = validated_data.pop('content_type')
        obj_id    = validated_data.pop('object_id')
        count     = validated_data.pop('count', 1)
        coupon_cd = validated_data.pop('coupon_code', None)
        attrs     = {
            k: validated_data.pop(k, None)
            for k in ('size','weight','material','color','flavor')
        }
        from .utils import add_to_cart_generic
        with transaction.atomic():
            ci = add_to_cart_generic(cart, ct, obj_id, attrs, count)
            if coupon_cd:
                try:
                    cp = Coupon.objects.get(code=coupon_cd)
                    if cp.is_active() and cp.can_user_use(self.context['request'].user):
                        ci.coupon = cp
                        ci.save(update_fields=['coupon'])
                except Coupon.DoesNotExist:
                    pass
            ci.refresh_from_db()
        return ci

    def update(self, instance, validated_data):
        # actualizar variantes y count
        changed = []
        for attr in ('size','weight','material','color','flavor','count'):
            if attr in validated_data:
                setattr(instance, attr, validated_data.pop(attr))
                changed.append(attr)
        # actualizar cupón de item
        if 'coupon_code' in self.initial_data:
            code = self.initial_data.get('coupon_code')
            if code == '':
                instance.coupon = None
            else:
                try:
                    instance.coupon = Coupon.objects.get(code=code)
                except Coupon.DoesNotExist:
                    instance.coupon = None
            changed.append('coupon')
        if changed:
            instance.save(update_fields=changed)
        return instance


class CartSerializer(serializers.ModelSerializer):
    items           = CartItemSerializer(many=True, read_only=True)
    total_items     = serializers.SerializerMethodField()
    subtotal        = serializers.SerializerMethodField()
    items_discount  = serializers.SerializerMethodField()
    cart_discount   = serializers.SerializerMethodField()
    discount_amount = serializers.SerializerMethodField()
    tax_amount      = serializers.SerializerMethodField()
    delivery_fee    = serializers.SerializerMethodField()
    total           = serializers.SerializerMethodField()

    shipping_address    = ShippingAddressSerializer(read_only=True)
    shipping_address_id = serializers.PrimaryKeyRelatedField(
        queryset=ShippingAddress.objects.all(),
        source='shipping_address',
        write_only=True,
        required=False,
        allow_null=True,
    )
    shipping_method    = ShippingMethodSerializer(read_only=True)
    shipping_method_id = serializers.PrimaryKeyRelatedField(
        queryset=ShippingMethod.objects.filter(active=True),
        source='shipping_method',
        write_only=True,
        required=False,
        allow_null=True,
    )
    shipping_cost = serializers.DecimalField(read_only=True, max_digits=8, decimal_places=2)

    coupon      = serializers.CharField(source='coupon.code', read_only=True)
    coupon_code = serializers.CharField(write_only=True, required=False)

    class Meta:
        model  = Cart
        fields = (
            'id', 'user', 'created_at',
            'items', 'total_items', 'subtotal', 'items_discount', 'cart_discount',
            'discount_amount', 'tax_amount', 'delivery_fee', 'total',
            'shipping_address', 'shipping_address_id',
            'shipping_method', 'shipping_method_id', 'shipping_cost',
            'coupon', 'coupon_code',
        )

    def get_total_items(self, obj):
        return sum(item.count for item in obj.items.all())

    def get_subtotal(self, obj):
        return obj.subtotal().quantize(Decimal('0.01'))

    def get_items_discount(self, obj):
        return obj.items_discount().quantize(Decimal('0.01'))

    def get_cart_discount(self, obj):
        cd, _ = obj.cart_discount()
        return cd.quantize(Decimal('0.01'))

    def get_discount_amount(self, obj):
        total = obj.items_discount() + obj.cart_discount()[0]
        return total.quantize(Decimal('0.01'))

    def get_delivery_fee(self, obj):
        _, free_ship = obj.cart_discount()
        return Decimal('0.00') if free_ship else obj.shipping_cost.quantize(Decimal('0.01'))

    def get_tax_amount(self, obj):
        rate = Decimal(settings.TAXES)
        taxable = obj.subtotal() - (obj.items_discount() + obj.cart_discount()[0])
        return (taxable * rate).quantize(Decimal('0.01'))

    def get_total(self, obj):
        """
        Total final incluyendo:
          - subtotal
          - descuentos de ítems
          - descuento de carrito
          - shipping
          - impuestos
        """
        pre_tax = obj.total()             # subtotal - discounts + shipping (sin impuesto)
        tax     = self.get_tax_amount(obj)  # ya cuantizado
        return (pre_tax + tax).quantize(Decimal('0.01'))

    def update(self, instance, validated_data):
        code = self.initial_data.get('coupon_code')
        if code is not None:
            instance.coupon = Coupon.objects.filter(code=code).first() if code else None
            instance.save(update_fields=['coupon'])
        instance = super().update(instance, validated_data)
        instance.recalc_shipping()
        return instance