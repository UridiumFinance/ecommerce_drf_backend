from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from .models import Wishlist, WishlistItem
from apps.products.serializers import (
    ProductSerializer,
    SizeSerializer,
    WeightSerializer,
    MaterialSerializer,
    ColorSerializer,
    FlavorSerializer,
)
from apps.products.models import Size, Weight, Material, Color, Flavor


# Mapea cada modelo a su serializer correspondiente
ITEM_SERIALIZERS = {
    'product': ProductSerializer,
    # 'course': CourseSerializer,
}


class PolymorphicRelatedField(serializers.RelatedField):
    """
    Selecciona el serializer según el modelo subyacente.
    """
    def to_representation(self, value):
        model_name = value._meta.model_name
        serializer_cls = ITEM_SERIALIZERS.get(model_name)
        if not serializer_cls:
            raise Exception(f"No hay serializer para modelo {model_name}")
        return serializer_cls(value, context=self.context).data


class WishlistItemSerializer(serializers.ModelSerializer):
    # Lectura
    item         = PolymorphicRelatedField(read_only=True)
    size         = serializers.SerializerMethodField()
    weight       = serializers.SerializerMethodField()
    material     = serializers.SerializerMethodField()
    color        = serializers.SerializerMethodField()
    flavor       = serializers.SerializerMethodField()
    added_at     = serializers.DateTimeField(read_only=True)
    updated_at   = serializers.DateTimeField(read_only=True)

    # Escritura
    content_type = serializers.SlugRelatedField(
        slug_field='model',
        queryset=ContentType.objects.filter(model__in=('product', 'course')),
        write_only=True
    )
    object_id    = serializers.UUIDField(write_only=True)
    size_id      = serializers.PrimaryKeyRelatedField(
        queryset=Size.objects.all(), source='size',
        write_only=True, allow_null=True, required=False
    )
    weight_id    = serializers.PrimaryKeyRelatedField(
        queryset=Weight.objects.all(), source='weight',
        write_only=True, allow_null=True, required=False
    )
    material_id  = serializers.PrimaryKeyRelatedField(
        queryset=Material.objects.all(), source='material',
        write_only=True, allow_null=True, required=False
    )
    color_id     = serializers.PrimaryKeyRelatedField(
        queryset=Color.objects.all(), source='color',
        write_only=True, allow_null=True, required=False
    )
    flavor_id    = serializers.PrimaryKeyRelatedField(
        queryset=Flavor.objects.all(), source='flavor',
        write_only=True, allow_null=True, required=False
    )

    class Meta:
        model = WishlistItem
        fields = (
            'id',
            'item',
            'size', 'weight', 'material', 'color', 'flavor',
            'added_at', 'updated_at',
            'content_type', 'object_id',
            'size_id', 'weight_id', 'material_id', 'color_id', 'flavor_id',
        )
        read_only_fields = ('item', 'size', 'weight', 'material', 'color', 'flavor', 'added_at', 'updated_at')

    def validate(self, data):
        ct = data.get('content_type') or getattr(self.instance, 'content_type', None)
        # Solo productos pueden llevar variantes
        if ct and ct.model != 'product':
            for fld in ('size_id', 'weight_id', 'material_id', 'color_id', 'flavor_id'):
                if self.initial_data.get(fld):
                    raise serializers.ValidationError("Solo productos admiten variantes.")
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

    def create(self, validated_data):
        wishlist   = self.context['wishlist']
        ct         = validated_data.pop('content_type')
        obj_id     = validated_data.pop('object_id')
        attrs      = {
            k: validated_data.pop(k, None)
            for k in ('size', 'weight', 'material', 'color', 'flavor')
        }
        # Crea el item; evita duplicados gracias a unique_together en el modelo
        item, created = WishlistItem.objects.get_or_create(
            wishlist=wishlist,
            content_type=ct,
            object_id=obj_id,
            defaults=attrs
        )
        if not created:
            # Si ya existía, actualiza variantes si cambian
            for k, v in attrs.items():
                if v and getattr(item, k) != v:
                    setattr(item, k, v)
            item.save(update_fields=[k for k in attrs if getattr(item, k) is not None])
        return item

    def update(self, instance, validated_data):
        # Permite actualizar solo variantes
        changed = []
        for attr in ('size', 'weight', 'material', 'color', 'flavor'):
            if attr in validated_data:
                setattr(instance, attr, validated_data.pop(attr))
                changed.append(attr)
        if changed:
            instance.save(update_fields=changed)
        return instance


class WishlistSerializer(serializers.ModelSerializer):
    items = WishlistItemSerializer(many=True, read_only=True)

    class Meta:
        model = Wishlist
        fields = ('id', 'items')
