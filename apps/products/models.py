import uuid
from datetime import timedelta
from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.conf import settings
from django.utils.html import format_html
from django.contrib import admin

from apps.assets.models import Media
from utils.s3_utils import get_cloudfront_signed_url


User = settings.AUTH_USER_MODEL



class Category(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent = models.ForeignKey("self", related_name="children", on_delete=models.CASCADE, blank=True, null=True)

    name = models.CharField(max_length=255)
    title = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    thumbnail = models.ForeignKey(
        Media,
        on_delete=models.SET_NULL,
        related_name='product_category_thumbnail',
        blank=True,
        null=True
    )
    slug = models.CharField(max_length=128)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    @admin.display(description="Thumbnail", ordering="thumbnail")
    def thumbnail_preview(self):
        if self.thumbnail and getattr(self.thumbnail, "key", None):
            try:
                url = get_cloudfront_signed_url(self.thumbnail.key)
                return format_html('<img src="{}" style="width: 50px; height: auto;" />', url)
            except Exception:
                return "URL inválida"
        return "—"
    
    class Meta:
        verbose_name_plural = "Categories"


class CategoryInteraction(models.Model):
    INTERACTION_CHOICES = (
        ("view", "View"),
        ("like", "Like"),
        ("share", "Share"),
        ("wishlist", "Wishlist"),
        ("add_to_cart", "Add to Cart"),
        ("remove_from_cart", "Remove from Cart"),
        ("purchase", "Purchase"),
        ("custom_event", "Custom Event"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, null=True, blank=True,
                             on_delete=models.SET_NULL,
                             related_name="user_category_interactions")
    
    category = models.ForeignKey(Category, on_delete=models.CASCADE,
                                 related_name="category_interactions")
    session_id = models.CharField(max_length=100, blank=True, null=True)
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_CHOICES)
    weight = models.FloatField(default=1.0)  # Importancia relativa
    metadata = models.JSONField(blank=True, null=True)

    ip_address = models.GenericIPAddressField(blank=True, null=True)
    device_type = models.CharField(max_length=50, blank=True, null=True,
                                   choices=(("desktop","Desktop"),
                                            ("mobile","Mobile"),
                                            ("tablet","Tablet")))
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name_plural = "Category Interactions"


class CategoryAnalytics(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.OneToOneField(Category, on_delete=models.CASCADE, related_name='category_analytics')
    
    # --- Tráfico general ---
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    click_through_rate = models.FloatField(default=0.0)  # En porcentaje
    views = models.PositiveIntegerField(default=0)
    last_viewed_at = models.DateTimeField(null=True, blank=True)
    first_viewed_at = models.DateTimeField(null=True, blank=True)
    avg_time_on_page = models.FloatField(default=0.0)    # En segundos

    # --- Interacciones sociales (agregadas) ---
    likes = models.PositiveIntegerField(default=0)
    shares = models.PositiveIntegerField(default=0)
    wishlist_count = models.PositiveIntegerField(default=0)

    # --- Conversiones y comercio ---
    add_to_cart_count = models.PositiveIntegerField(default=0)
    purchases = models.PositiveIntegerField(default=0)
    conversion_rate = models.FloatField(default=0.0)      # (purchases / views) * 100
    revenue_generated = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    avg_order_value = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    # --- Timestamps ---
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Category Analytics"

    def __str__(self):
        return f"Analytics for category {self.category.name}"
    
    def _update_click_through_rate(self):
        if self.impressions > 0:
            self.click_through_rate = (self.clicks / self.impressions) * 100
        else:
            self.click_through_rate = 0.0
        self.save(update_fields=["click_through_rate"])

    def _update_conversion_rate(self):
        if self.views > 0:
            self.conversion_rate = (self.purchases / self.views) * 100
        else:
            self.conversion_rate = 0.0
        self.save(update_fields=["conversion_rate"])

    def _update_avg_order_value(self):
        if self.purchases > 0:
            self.avg_order_value = float(self.revenue_generated) / self.purchases
        else:
            self.avg_order_value = 0.0
        self.save(update_fields=["avg_order_value"])

    def increment_metric(self, metric_name, amount=1):
        """
        Incrementa una métrica simple y actualiza derivadas si aplica.
        """
        if not hasattr(self, metric_name):
            raise ValueError(f"Metric '{metric_name}' does not exist in CategoryAnalytics")

        current = getattr(self, metric_name)
        setattr(self, metric_name, current + amount)
        self.save(update_fields=[metric_name])

        derived_map = {
            'clicks': self._update_click_through_rate,
            'impressions': self._update_click_through_rate,
            'views': self._update_conversion_rate,
            'purchases': [self._update_conversion_rate, self._update_avg_order_value],
            'revenue_generated': self._update_avg_order_value,
        }

        update_func = derived_map.get(metric_name)
        if update_func:
            if isinstance(update_func, list):
                for f in update_func:
                    f()
            else:
                update_func()


class Product(models.Model):
    # --- Identificación básica ---
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.UUIDField(default=uuid.uuid4, editable=False)

    # --- Información del producto ---
    title = models.CharField(max_length=255, blank=True, null=True)
    short_description = models.TextField(max_length=169, blank=True, null=True, default="")
    description = models.TextField(blank=True, null=True, default="")
    keywords = models.CharField(max_length=255, blank=True, null=True)

    # --- Multimedia ---
    images = models.ManyToManyField(
        Media,
        blank=True,
        related_name="product_images",
        limit_choices_to={"media_type": "image"},
    )
    thumbnail = models.ForeignKey(
        Media,
        null=True,
        blank=True,
        limit_choices_to={"media_type": "image"},
        on_delete=models.SET_NULL,
        related_name="thumbnail_for_product",
        verbose_name="Thumbnail"
    )

    # --- Categorias ---
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="product_category",
    )
    sub_category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="product_sub_category",
    )
    topic = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="product_topic",
    )

    # --- URL amigable ---
    slug = models.SlugField(unique=True, default=uuid.uuid4)

    # --- Control de precios y promociones ---
    price = models.DecimalField(max_digits=6, decimal_places=2, blank=True,
                                null=True, default=Decimal('2.00'))
    compare_price = models.DecimalField(max_digits=6, decimal_places=2,
                                        blank=True, null=True, default=Decimal('0.00'))
    discount = models.BooleanField(default=False)
    discount_until = models.DateTimeField(default=timezone.now,
                                          blank=True, null=True)

    # --- Inventario y disponibilidad ---
    stock = models.IntegerField(default=0, blank=True, null=True)
    hidden = models.BooleanField(default=False)
    banned = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=True)
    limited_edition = models.BooleanField(default=False)

    # --- Condición física del producto ---
    condition = models.CharField(
        max_length=255,
        choices=(("new", "New"), ("used", "Used"), ("broken", "Broken")),
        default="new"
    )

    packaging = models.CharField(
        max_length=255,
        choices=(("normal", "Normal"), ("gift", "Gift")),
        default="normal"
    )

    # --- Estado de publicación ---
    status = models.CharField(
        max_length=10,
        choices=(("draft", "Draft"), ("published", "Published")),
        default="draft"
    )

    # --- Fechas de control ---
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # --- Managers ---
    objects = models.Manager()
    class PostObjects(models.Manager):
        def get_queryset(self):
            return super().get_queryset().filter(status="published", hidden=False, banned=False)
    postobjects = PostObjects()

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return self.title or "Sin título"
    
    def get_first_image(self):
        if self.thumbnail:
            return self.thumbnail
        if self.images.exists():
            return self.images.first()
        return None
    
    @admin.display(description="Thumbnail", ordering="thumbnail")
    def thumbnail_preview(self):
        first = self.get_first_image()
        if first and getattr(first, "key", None):
            try:
                url = get_cloudfront_signed_url(first.key)
                return format_html('<img src="{}" style="width: 50px; height: auto;" />', url)
            except Exception:
                return "URL inválida"
        return "—"
    
    @property
    def total_stock(self) -> int:
        """
        Suma el stock de todos los atributos relacionados.
        """
        total = 0
        # Estas relaciones vienen de ProductAttributeBase:
        for rel in ('colors', 'sizes', 'materials', 'weights', 'flavors'):
            qs = getattr(self, rel).all()
            # sumamos solo los que tienen stock definido
            total += sum((attr.stock or 0) for attr in qs)
        return total
    
    @property
    def total_attributes_price(self) -> Decimal:
        """
        Suma el precio de todos los atributos relacionados.
        """
        total = Decimal('0.00')
        for rel in ('colors', 'sizes', 'materials', 'weights', 'flavors'):
            total += sum((attr.price or Decimal('0.00')) for attr in getattr(self, rel).all())
        return total

    def get_discount_rate(self) -> Decimal:
        """
        Proporción de descuento (0–1) basada en compare_price vs price,
        sólo si discount=True y discount_until está en el futuro.
        """
        if not self.discount or not self.compare_price:
            return Decimal('0.00')
        now = timezone.now()
        if self.discount_until and self.discount_until > now:
            cp = self.compare_price
            p  = self.price or Decimal('0.00')
            if cp > p:
                return (cp - p) / cp
        return Decimal('0.00')

    def get_price_with_selected(self, selected_attrs: dict) -> Decimal:
        """
        Precio base (self.price) + suma de precios de variantes seleccionadas.
        No reaplica descuentos: asumimos que `self.price` ya está en valor descontado.
        """
        total = self.price or Decimal('0.00')
        for attr in selected_attrs.values():
            # sólo sumar si la variante tiene precio
            if getattr(attr, 'price', None) is not None:
                total += attr.price
        # aseguramos 2 decimales
        return total.quantize(Decimal('0.01'))

    def get_unit_price(self) -> Decimal:
        """
        Precio unitario sin variantes, usando la misma lógica de arriba.
        """
        return self.get_price_with_selected({})

    # Si quieres mostrar el precio 'anterior', podrías usar:
    @property
    def original_price(self) -> Decimal:
        """
        Precio antes de descuento (compare_price), o None si no hay compare_price.
        """
        return self.compare_price if self.compare_price and self.compare_price > self.price else None
    
    def get_slug(self):
        return self.slug

    
class ProductInteraction(models.Model):
    # --- Tipos y categorías de interacción ---
    INTERACTION_CHOICES = (
        ("view", "View"),
        ("like", "Like"),
        ("share", "Share"),
        ("rate", "Rate"),
        ("wishlist", "Wishlist"),
        ("add_to_cart", "Add to Cart"),
        ("remove_from_cart", "Remove from Cart"),
        ("purchase", "Purchase"),
        ("custom_event", "Custom Event"),
    )

    INTERACTION_TYPE_CATEGORIES = (
        ("passive", "Passive"),
        ("active", "Active"),
    )

    # --- Identificadores clave ---
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='user_product_interactions')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_interactions')
    session_id = models.CharField(max_length=100, blank=True, null=True)  # Para usuarios anónimos

    # --- Tipo de interacción y metadatos ---
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_CHOICES)
    interaction_category = models.CharField(max_length=10, choices=INTERACTION_TYPE_CATEGORIES, default="passive")
    weight = models.FloatField(default=1.0)  # Importancia relativa
    metadata = models.JSONField(blank=True, null=True)  # Datos adicionales arbitrarios

    # --- Campos contextuales según tipo de interacción ---
    rating = models.IntegerField(blank=True, null=True)  # Solo si interaction_type == "rate"
    review = models.TextField(blank=True, null=True)     # Solo si interaction_type == "rate"
    quantity = models.PositiveIntegerField(blank=True, null=True)  # "add_to_cart", "purchase"
    total_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    order_id = models.CharField(max_length=100, blank=True, null=True)

    # --- Datos de trazabilidad del evento ---
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    device_type = models.CharField(
        max_length=50, blank=True, null=True,
        choices=(("desktop", "Desktop"), ("mobile", "Mobile"), ("tablet", "Tablet"))
    )
    hour_of_day = models.IntegerField(null=True, blank=True)
    day_of_week = models.IntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def save(self, *args, **kwargs):
        # Auto-set categoría
        if self.interaction_type in ["view", "wishlist"]:
            self.interaction_category = "passive"
        else:
            self.interaction_category = "active"

        # Hora y día para analítica de comportamiento
        now = timezone.now()
        self.hour_of_day = now.hour
        self.day_of_week = now.weekday()

        super().save(*args, **kwargs)

    def __str__(self):
        username = self.user.username if self.user else "Anonymous"
        return f"{username} {self.interaction_type} {self.product.title}"
    
    def save(self, *args, **kwargs):
        # --- Detección de anomalías antes de guardar ---
        if is_anomalous_interaction(
            user=self.user,
            product=self.product,
            ip_address=self.ip_address,
            interaction_type=self.interaction_type,
            window_minutes=3,
            threshold=30
        ):
            raise ValueError("Comportamiento anómalo detectado. Esta interacción ha sido bloqueada.")

        # --- Asignación de campos automáticos ---
        passive_types = ["view", "wishlist"]
        self.interaction_category = "passive" if self.interaction_type in passive_types else "active"

        now = timezone.now()
        self.hour_of_day = now.hour
        self.day_of_week = now.weekday()

        super().save(*args, **kwargs)
    

class ProductAnalytics(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='product_analytics')

    # --- Tráfico general ---
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    click_through_rate = models.FloatField(default=0.0)  # CTR = (clicks / impressions) * 100
    avg_time_on_page = models.FloatField(default=0.0)    # En segundos
    views = models.PositiveIntegerField(default=0)
    last_viewed_at = models.DateTimeField(null=True, blank=True)
    first_viewed_at = models.DateTimeField(null=True, blank=True)

    # --- Interacciones sociales ---
    likes = models.PositiveIntegerField(default=0)
    shares = models.PositiveIntegerField(default=0)
    wishlist_count = models.PositiveIntegerField(default=0)

    # --- Interacciones de compra y carrito ---
    add_to_cart_count = models.PositiveIntegerField(default=0)
    remove_from_cart_count = models.PositiveIntegerField(default=0)
    purchases = models.PositiveIntegerField(default=0)
    conversion_rate = models.FloatField(default=0.0)         # (purchases / views) * 100
    cart_abandonment_rate = models.FloatField(default=0.0)   # (added - purchased) / added

    # --- Ingresos ---
    revenue_generated = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    avg_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # --- Valoraciones ---
    average_rating = models.FloatField(default=0.0)
    review_count = models.PositiveIntegerField(default=0)

    # --- Logística ---
    returns_count = models.PositiveIntegerField(default=0)
    stockouts_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Product Analytics"

    def __str__(self):
        return f"Analytics for {self.product.title}"
    
    def _update_click_through_rate(self):
        if self.impressions > 0:
            self.click_through_rate = (self.clicks/self.impressions) * 100
        else:
            self.click_through_rate = 0
        self.save(update_fields=["click_through_rate"])

    def _update_conversion_rate(self):
        if self.views > 0:
            self.conversion_rate = (self.purchases / self.views) * 100
        else:
            self.conversion_rate = 0.0
        self.save(update_fields=["conversion_rate"])

    def _update_cart_abandonment_rate(self):
        if self.add_to_cart_count > 0:
            abandoned = self.add_to_cart_count - self.purchases
            self.cart_abandonment_rate = (abandoned / self.add_to_cart_count) * 100
        else:
            self.cart_abandonment_rate = 0.0
        self.save(update_fields=["cart_abandonment_rate"])

    def _update_avg_order_value(self):
        if self.purchases > 0:
            self.avg_order_value = float(self.revenue_generated) / self.purchases
        else:
            self.avg_order_value = 0.0
        self.save(update_fields=["avg_order_value"])
    
    def increment_metric(self, metric_name, amount=1):
        """
        Incrementa una métrica simple y actualiza derivadas si aplica.
        """
        if not hasattr(self, metric_name):
            raise ValueError(f"Metric '{metric_name}' does not exist in ProductAnalytics")

        current_value = getattr(self, metric_name)
        setattr(self, metric_name, current_value + amount)
        self.save(update_fields=[metric_name])

        # Actualizar métricas derivadas si aplica
        derived_map = {
            "clicks": self._update_click_through_rate,
            "impressions": self._update_click_through_rate,
            "purchases": [self._update_conversion_rate, self._update_cart_abandonment_rate, self._update_avg_order_value],
            "views": self._update_conversion_rate,
            "add_to_cart_count": self._update_cart_abandonment_rate,
            "revenue_generated": self._update_avg_order_value,
        }

        # Ejecutar derivadas
        update_func = derived_map.get(metric_name)
        if update_func:
            if isinstance(update_func, list):
                for f in update_func:
                    f()
            else:
                update_func()


class Detail(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.PositiveIntegerField(null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="details")
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class Requisite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.PositiveIntegerField(null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="requisites")
    title = models.CharField(max_length=255)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title
    

class Benefit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.PositiveIntegerField(null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="benefits")
    title = models.CharField(max_length=255)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title
    

class WhoIsFor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.PositiveIntegerField(null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="target_audience")
    title = models.CharField(max_length=255)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class ProductAttributeBase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.PositiveIntegerField(null=True, blank=True, help_text="Orden de aparición.")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    stock = models.IntegerField(null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ['order']

    def __str__(self):
        return self.title
    
    
    
# Modelos heredados
class Color(ProductAttributeBase):
    hex = models.CharField(max_length=7, help_text="Código HEX (ej. #FFFFFF)")

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="colors",
    )

class Size(ProductAttributeBase):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="sizes",
    )

class Material(ProductAttributeBase):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="materials",
    )

class Weight(ProductAttributeBase):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="weights",
    )

class Flavor(ProductAttributeBase):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="flavors",
    )


def is_anomalous_interaction(user, product, ip_address, interaction_type, window_minutes=5, threshold=20):
    """
    Detecta si el número de interacciones recientes excede un umbral (spam).
    Se puede aplicar a usuario o IP.
    """
    now = timezone.now()
    time_threshold = now - timedelta(minutes=window_minutes)

    # Filtrar interacciones recientes por tipo
    queryset = ProductInteraction.objects.filter(
        product=product,
        interaction_type=interaction_type,
        timestamp__gte=time_threshold,
    )

    # Filtrar por usuario o IP si es anónimo
    if user:
        queryset = queryset.filter(user=user)
    elif ip_address:
        queryset = queryset.filter(ip_address=ip_address)

    return queryset.count() > threshold