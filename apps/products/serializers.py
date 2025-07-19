from rest_framework import serializers
from django.utils import timezone
from decimal import Decimal

from apps.assets.serializers import MediaSerializer
from .models import (
    Product, ProductInteraction, ProductAnalytics, 
    Detail, Requisite, Benefit, WhoIsFor,
    Color, Size, Material, Weight, Flavor,
    Category, CategoryInteraction, CategoryAnalytics
)
from apps.reviews.serializers import ReviewSerializer

class CategoryNestedSerializer(serializers.ModelSerializer):
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Category
        # Ajusta los campos que quieras exponer en el anidado
        fields = ('id', 'name', 'slug', 'thumbnail')

    def get_thumbnail(self, obj):
        if obj.thumbnail:
            # Propaga self.context (incluye expires_in si lo definiste)
            return MediaSerializer(obj.thumbnail, context=self.context).data.get('url')
        return None
    

class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer para Category; incluye thumbnail y árbol de categorías hijas.
    """
    thumbnail = serializers.SerializerMethodField()
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), allow_null=True, required=False
    )
    children = serializers.SerializerMethodField()

    analytics_views        = serializers.IntegerField(read_only=True, required=False)
    analytics_likes        = serializers.IntegerField(read_only=True, required=False)
    analytics_shares       = serializers.IntegerField(read_only=True, required=False)
    analytics_wishlist     = serializers.IntegerField(read_only=True, required=False)
    analytics_add_to_cart  = serializers.IntegerField(read_only=True, required=False)
    analytics_purchases    = serializers.IntegerField(read_only=True, required=False)
    analytics_revenue      = serializers.DecimalField(
        read_only=True, max_digits=12, decimal_places=2, required=False
    )

    related_categories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = '__all__'

    def get_children(self, obj):
        qs = obj.children.all()
        return CategorySerializer(qs, many=True, context=self.context).data
    
    def get_thumbnail(self, obj):
        if obj.thumbnail:
            return MediaSerializer(obj.thumbnail, context=self.context).data.get('url')
        return None
    
    def get_related_categories(self, obj):
        """
        Devuelve un listado de categorías relacionadas:
          - El padre (si existe)
          - Los hijos directos
          - Los hermanos (otros hijos del mismo padre)
        """
        related = []
        # 1) padre
        if obj.parent:
            related.append(obj.parent)

            # 2) hermanos
            siblings = obj.parent.children.exclude(pk=obj.pk)
            related.extend(siblings)

        # 3) hijos
        related.extend(obj.children.all())

        # Quitar duplicados por id y serializar
        unique = {c.pk: c for c in related}.values()
        return CategoryNestedSerializer(unique, many=True, context=self.context).data


class CategoryInteractionSerializer(serializers.ModelSerializer):
    """
    Serializer para crear y listar interacciones sobre categorías.
    """
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all()
    )
    timestamp = serializers.DateTimeField(read_only=True, default=timezone.now)

    class Meta:
        model = CategoryInteraction
        fields = (
            'id', 'user', 'category', 'session_id',
            'interaction_type', 'metadata',
            'ip_address', 'device_type', 'timestamp'
        )


class CategoryAnalyticsSerializer(serializers.ModelSerializer):
    """
    Serializer para exponer las métricas agregadas de una categoría.
    """
    category = CategorySerializer(read_only=True)

    class Meta:
        model = CategoryAnalytics
        fields = (
            'id', 'category',
            # Tráfico general
            'impressions', 'clicks', 'click_through_rate',
            'views', 'first_viewed_at', 'last_viewed_at',
            'avg_time_on_page',
            # Interacciones sociales
            'likes', 'shares', 'wishlist_count',
            # Comercio
            'add_to_cart_count', 'purchases',
            'conversion_rate', 'revenue_generated',
            'avg_order_value',
            # Timestamps
            'created_at', 'updated_at',
        )
        read_only_fields = fields

# --- Serializers para atributos simples ---

class DetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Detail
        fields = ('id', 'order', 'title', 'description')


class RequisiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Requisite
        fields = ('id', 'order', 'title')


class BenefitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Benefit
        fields = ('id', 'order', 'title')


class WhoIsForSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhoIsFor
        fields = ('id', 'order', 'title')


# --- Serializers para atributos con precio y stock ---

class ColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Color
        fields = ('id', 'order', 'title', 'hex', 'price', 'stock')


class SizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Size
        fields = ('id', 'order', 'title', 'price', 'stock')


class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = ('id', 'order', 'title', 'price', 'stock')


class WeightSerializer(serializers.ModelSerializer):
    class Meta:
        model = Weight
        fields = ('id', 'order', 'title', 'price', 'stock')


class FlavorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Flavor
        fields = ('id', 'order', 'title', 'price', 'stock')


# --- Serializador principal del producto con atributos anidados ---
class ProductListSerializer(serializers.ModelSerializer):
    thumbnail       = serializers.SerializerMethodField()
    average_rating  = serializers.FloatField(source='analytics_avg_rating', read_only=True)
    review_count    = serializers.IntegerField(source='analytics_review_count', read_only=True)
    category        = CategorySerializer()
    sub_category    = CategorySerializer()
    topic           = CategorySerializer()
    stock           = serializers.IntegerField(source='total_stock', read_only=True)
    min_price       = serializers.SerializerMethodField()

    colors          = ColorSerializer(many=True, required=False)
    sizes           = SizeSerializer(many=True, required=False)
    materials       = MaterialSerializer(many=True, required=False)
    weights         = WeightSerializer(many=True, required=False)
    flavors         = FlavorSerializer(many=True, required=False)

    class Meta:
        model = Product
        fields = [
            'id', 'author',
            'title', 'short_description',
            'slug',
            'price', 'compare_price', 'discount', 'discount_until',
            'stock', 'limited_edition', 'condition',
            'thumbnail', 'average_rating', 'review_count',
            'category', 'sub_category', 'topic', 'min_price',
            'colors',
            'sizes',
            'materials',
            'weights',
            'flavors',
        ]

    def get_thumbnail(self, obj):
        image = obj.get_first_image()
        if not image:
            return None
        # aquí ponemos 1 hora (3600 s)
        return MediaSerializer(obj.thumbnail, context=self.context).data.get('url')
    
    def get_min_price(self, obj):
        total = obj.price or Decimal('0.00')
        # Por cada tipo de atributo, sumamos el más barato
        for rel in ('colors','sizes','materials','weights','flavors'):
            precios = [a.price for a in getattr(obj, rel).all() if a.price]
            if precios:
                total += min(precios)
        return total


class ProductSerializer(serializers.ModelSerializer):

    details          = DetailSerializer(many=True, required=False)
    requisites       = RequisiteSerializer(many=True, required=False)
    benefits         = BenefitSerializer(many=True, required=False)
    target_audience  = WhoIsForSerializer(many=True, required=False)

    colors    = ColorSerializer(many=True, required=False)
    sizes     = SizeSerializer(many=True, required=False)
    materials = MaterialSerializer(many=True, required=False)
    weights   = WeightSerializer(many=True, required=False)
    flavors   = FlavorSerializer(many=True, required=False)

    thumbnail  = serializers.SerializerMethodField()
    images     = serializers.SerializerMethodField()
    has_liked  = serializers.SerializerMethodField()

    average_rating = serializers.FloatField(source='analytics_avg_rating', read_only=True)
    review_count   = serializers.IntegerField(source='analytics_review_count', read_only=True)
    # reviews = serializers.SerializerMethodField()

    category     = CategorySerializer(read_only=True)
    sub_category = CategorySerializer(read_only=True)
    topic        = CategorySerializer(read_only=True)
    
    # Override stock to reflect sum of attribute stocks
    stock = serializers.IntegerField(source='total_stock', read_only=True)


    price_with_all_attributes = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )
    price_with_selected = serializers.SerializerMethodField()
    total_attributes_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = Product
        # Mantener todos los campos del modelo
        fields = '__all__'

    def get_thumbnail(self, obj):
        image = obj.get_first_image()
        if not image:
            return None
        ctx = { **self.context, 'expires_in': 60 * 60 * 24 }

        # 3) pasamos la instancia correcta y el context
        return MediaSerializer(image, context=ctx).data['url']

    def get_images(self, obj):
        urls = []
        # aquí ponemos None → sin expiración / sin firma
        ctx = {**self.context, 'expires_in': 3600}
        for image in obj.images.all():
            if not getattr(image, 'key', None):
                continue
            urls.append(MediaSerializer(image, context=ctx).data['url'])
        return urls

    def get_has_liked(self, obj):
        request = self.context.get("request")
        if not request:
            return False

        user = request.user if request.user.is_authenticated else None
        session_id = request.session.session_key
        if not session_id:
            request.session.save()
            session_id = request.session.session_key

        filter_kwargs = {"product": obj, "interaction_type": "like"}
        if user:
            filter_kwargs["user"] = user
        else:
            filter_kwargs["session_id"] = session_id

        return ProductInteraction.objects.filter(**filter_kwargs).exists()
    
    def get_price_with_selected(self, obj):
        # Extrae dict de atributos seleccionados desde el contexto
        selected = self.context.get('selected_attributes', {}) or {}
        return obj.get_price_with_selected(selected)
    
    # def get_reviews(self, obj):
    #     """
    #     Devuelve las reseñas activas, ordenadas por created_at desc.
    #     """
    #     qs = obj.reviews.filter(is_active=True).order_by('-created_at')
    #     return ReviewSerializer(qs, many=True, context=self.context).data


class ProductWithMetricsSerializer(ProductSerializer):
    views = serializers.SerializerMethodField()
    likes = serializers.SerializerMethodField()
    shares = serializers.SerializerMethodField()
    wishlist_count = serializers.SerializerMethodField()
    purchases = serializers.SerializerMethodField()
    revenue_generated = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    class Meta(ProductSerializer.Meta):
        fields = '__all__'

    def get_views(self, obj):
        return getattr(obj.product_analytics, "views", 0)

    def get_likes(self, obj):
        return getattr(obj.product_analytics, "likes", 0)

    def get_shares(self, obj):
        return getattr(obj.product_analytics, "shares", 0)

    def get_wishlist_count(self, obj):
        return getattr(obj.product_analytics, "wishlist_count", 0)

    def get_purchases(self, obj):
        return getattr(obj.product_analytics, "purchases", 0)

    def get_revenue_generated(self, obj):
        revenue = getattr(obj.product_analytics, "revenue_generated", None)
        return float(revenue) if revenue is not None else 0.0

    def get_average_rating(self, obj):
        return getattr(obj.product_analytics, "average_rating", 0.0)

    def get_review_count(self, obj):
        return getattr(obj.product_analytics, "review_count", 0)
    

class ProductInteractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductInteraction
        fields = [
            'id', 'user', 'product', 'session_id',
            'interaction_type', 'interaction_category', 'weight',
            'metadata', 'rating', 'review', 'quantity',
            'total_price', 'order_id', 'ip_address', 'device_type',
            'hour_of_day', 'day_of_week', 'timestamp'
        ]
        read_only_fields = ('interaction_category', 'hour_of_day', 'day_of_week', 'timestamp')

    def create(self, validated_data):
        return ProductInteraction.objects.create(**validated_data)
    

class ProductAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAnalytics
        fields = '__all__'

