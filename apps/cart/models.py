import uuid
from decimal import Decimal
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django_countries.fields import CountryField
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from apps.products.models import Size, Weight, Material, Color, Flavor
from apps.addresses.models import ShippingAddress


class ShippingProvider(models.Model):
    """
    Una API o empresa de mensajería (DHL, FedEx, Correos, Mensajeros locales…).
    """
    name    = models.CharField(max_length=100, unique=True)
    code    = models.SlugField(max_length=50, unique=True)
    active  = models.BooleanField(default=True)
    api_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name


class ShippingZone(models.Model):
    """
    Agrupa países o regiones a las que se aplica una tarifa determinada.
    Ej: “Perú continental”, “Europa UE”, “Resto del mundo”.
    """
    name      = models.CharField(max_length=100, unique=True)
    countries = CountryField(multiple=True)

    def __str__(self):
        return self.name


class ShippingMethod(models.Model):
    """
    Una opción de envío concreta: provider + velocidad + zona + esquema de tarifas.
    """
    provider          = models.ForeignKey(ShippingProvider,
                                          on_delete=models.PROTECT,
                                          related_name="methods")
    zone              = models.ForeignKey(ShippingZone,
                                          on_delete=models.PROTECT,
                                          related_name="methods")
    name              = models.CharField(max_length=100)
    code              = models.SlugField(max_length=50)
    base_rate         = models.DecimalField(max_digits=8,
                                            decimal_places=2,
                                            help_text="Costo fijo por envío")
    per_kg_rate       = models.DecimalField(max_digits=8,
                                            decimal_places=2,
                                            help_text="Costo por kilogramo adicional")
    min_delivery_days = models.PositiveSmallIntegerField()
    max_delivery_days = models.PositiveSmallIntegerField()
    active            = models.BooleanField(default=True)

    class Meta:
        unique_together = [("provider", "zone", "code")]

    def __str__(self):
        return f"{self.provider.name} – {self.name} ({self.zone.name})"

    def calculate_cost(self, total_weight_kg: Decimal) -> Decimal:
        """
        Devuelve base_rate + per_kg_rate * (total_weight_kg − 1), garantizando al menos base_rate.
        """
        extra_kg = max(total_weight_kg - Decimal('1.0'), Decimal('0'))
        return (self.base_rate + extra_kg * self.per_kg_rate).quantize(Decimal('0.01'))


class Coupon(models.Model):
    FIXED         = 'fixed'
    PERCENT       = 'percent'
    FREE_SHIPPING = 'free_shipping'

    TYPE_CHOICES  = [
        (FIXED,         'Importe fijo'),
        (PERCENT,       'Porcentaje'),
        (FREE_SHIPPING, 'Envío gratis'),
    ]

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code           = models.CharField(max_length=50, unique=True)
    description    = models.CharField(max_length=255, blank=True)

    coupon_type    = models.CharField(max_length=20, choices=TYPE_CHOICES, default=PERCENT)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    valid_from     = models.DateTimeField()
    valid_to       = models.DateTimeField()
    active         = models.BooleanField(default=True)

    max_uses       = models.PositiveIntegerField(null=True, blank=True)
    per_user_limit = models.PositiveIntegerField(default=1)

    min_subtotal   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    max_subtotal   = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    countries      = CountryField(multiple=True, blank=True)
    uses_count     = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-valid_from']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['valid_to']),
        ]

    def __str__(self):
        return self.code

    def is_active(self) -> bool:
        now = timezone.now()
        if not self.active or not (self.valid_from <= now <= self.valid_to):
            return False
        if self.max_uses is not None and self.uses_count >= self.max_uses:
            return False
        return True

    def can_user_use(self, user) -> bool:
        if not self.is_active():
            return False
        used = self.redemptions.filter(user=user).count()
        return used < self.per_user_limit

    def apply_discount(self, subtotal: Decimal, shipping_cost: Decimal = Decimal('0.00')) -> (Decimal, bool):
        """
        Descuento global para el carrito completo.
        Devuelve (monto_descuento, free_shipping_flag).
        """
        # Validar rango de subtotal
        if subtotal < self.min_subtotal or (self.max_subtotal is not None and subtotal > self.max_subtotal):
            return Decimal('0.00'), False

        discount_amount = Decimal('0.00')
        free_shipping   = False

        if self.coupon_type == self.PERCENT:
            discount_amount = (subtotal * self.discount_value / Decimal('100')).quantize(Decimal('0.01'))
        elif self.coupon_type == self.FIXED:
            discount_amount = min(self.discount_value, subtotal)
        elif self.coupon_type == self.FREE_SHIPPING:
            free_shipping = True

        return discount_amount, free_shipping

    def apply_item_discount(self, unit_price: Decimal, quantity: int) -> Decimal:
        """
        Descuento aplicado a un único CartItem.
        Devuelve solo el monto de descuento.
        """
        line_total = (unit_price * quantity).quantize(Decimal('0.01'))
        if line_total < self.min_subtotal or (self.max_subtotal and line_total > self.max_subtotal):
            return Decimal('0.00')

        if self.coupon_type == self.PERCENT:
            return (line_total * self.discount_value / Decimal('100')).quantize(Decimal('0.01'))
        elif self.coupon_type == self.FIXED:
            # Si es fijo, se resta hasta ese monto por línea
            return min(self.discount_value, line_total)

        return Decimal('0.00')

    def record_usage(self, user, order=None):
        """
        Registrar el canje del cupón:
         - Incrementa uses_count
         - Crea un CouponRedemption
        """
        # Incrementar contador de usos
        self.uses_count = models.F('uses_count') + 1
        self.save(update_fields=['uses_count'])

        # Registrar la redención
        from .models import CouponRedemption
        CouponRedemption.objects.create(
            coupon=self,
            user=user,
            order=order,
            redeemed_at=timezone.now()
        )


class CouponRedemption(models.Model):
    coupon      = models.ForeignKey(Coupon,
                                    on_delete=models.CASCADE,
                                    related_name='redemptions')
    user        = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.CASCADE)
    order       = models.UUIDField(null=True, blank=True)
    redeemed_at = models.DateTimeField()

    class Meta:
        unique_together = [('coupon','user','order')]
        ordering = ['-redeemed_at']


class Cart(models.Model):
    """
    El carrito de un usuario, con items genéricos y lógica de envío.
    """
    id               = models.UUIDField(primary_key=True,
                                        default=uuid.uuid4,
                                        editable=False)
    user             = models.UUIDField(default=uuid.uuid4,
                                        editable=False,
                                        unique=True)
    created_at       = models.DateTimeField(auto_now_add=True, db_index=True)

    shipping_address = models.ForeignKey(
        ShippingAddress,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    shipping_method  = models.ForeignKey(
        ShippingMethod,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    shipping_cost    = models.DecimalField(max_digits=8,
                                           decimal_places=2,
                                           default=Decimal('0.00'))

    coupon           = models.ForeignKey(
        Coupon,
        null=True, blank=True,
        on_delete=models.SET_NULL
    )

    class Meta:
        indexes = [models.Index(fields=['user'])]

    def total_weight_kg(self) -> Decimal:
        total = Decimal('0')
        for ci in self.items.select_related('weight').all():
            w = ci.weight
            if w and hasattr(w, 'weight_kg'):
                total += w.weight_kg * ci.count
        return total

    def recalc_shipping(self):
        """Recalcula shipping_cost"""
        _, free_ship = self.cart_discount()
        if free_ship:
            self.shipping_cost = Decimal('0.00')
        elif not self.shipping_address or not self.shipping_method:
            self.shipping_cost = Decimal('0.00')
        else:
            w = self.total_weight_kg()
            self.shipping_cost = self.shipping_method.calculate_cost(w)
        self.save(update_fields=['shipping_cost'])

    def subtotal(self) -> Decimal:
        """Suma precios sin descuentos, garantizando Decimal como resultado."""
        return sum(
            (ci.unit_price() * ci.count for ci in self.items.all()),
            Decimal('0.00')
        )

    def items_discount(self) -> Decimal:
        """Suma descuentos por ítem, garantizando Decimal."""
        return sum(
            (ci.discount_amount for ci in self.items.all()),
            Decimal('0.00')
        )

    def cart_discount(self) -> (Decimal, bool):
        """Descuento global sobre subtotal neto de ítems."""
        sub_n = self.subtotal() - self.items_discount()
        if not self.coupon:
            return Decimal('0.00'), False
        return self.coupon.apply_discount(sub_n, self.shipping_cost)

    def total(self) -> Decimal:
        """Total final: subtotal - discounts + shipping."""
        sub = self.subtotal()
        di = self.items_discount()
        dc, free = self.cart_discount()
        ship = Decimal('0.00') if free else self.shipping_cost
        return (sub - di - dc + ship).quantize(Decimal('0.01'))

    def __str__(self):
        return f"Cart {self.id}"


class CartItem(models.Model):
    """Un ítem genérico en un carrito."""
    id           = models.UUIDField(primary_key=True,
                                    default=uuid.uuid4,
                                    editable=False)
    cart         = models.ForeignKey(Cart,
                                     on_delete=models.CASCADE,
                                     related_name='items')
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={'model__in': ('product', 'course')},
        null=True, blank=True
    )
    object_id    = models.UUIDField(null=True, blank=True)
    item         = GenericForeignKey('content_type', 'object_id')

    size         = models.ForeignKey(Size, on_delete=models.SET_NULL, null=True, blank=True)
    weight       = models.ForeignKey(Weight, on_delete=models.SET_NULL, null=True, blank=True)
    material     = models.ForeignKey(Material, on_delete=models.SET_NULL, null=True, blank=True)
    color        = models.ForeignKey(Color, on_delete=models.SET_NULL, null=True, blank=True)
    flavor       = models.ForeignKey(Flavor, on_delete=models.SET_NULL, null=True, blank=True)

    count        = models.PositiveIntegerField(default=1)
    coupon       = models.ForeignKey(Coupon, null=True, blank=True, on_delete=models.SET_NULL)
    added_at     = models.DateTimeField(default=timezone.now, editable=False, db_index=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [
            ("cart", "content_type", "object_id",
             "size", "weight", "material", "color", "flavor"),
        ]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def time_in_cart(self) -> timedelta:
        """
        Tiempo transcurrido desde que el ítem fue agregado.
        """
        return timezone.now() - self.added_at

    def unit_price(self) -> Decimal:
        """
        Precio unitario incluyendo variantes:
        1) recoge las variantes seleccionadas en este CartItem,
        2) llama a Product.get_price_with_selected(selected_attrs),
        3) cuantiza a 2 decimales.
        """
        from decimal import Decimal

        prod = self.item
        if not prod:
            return Decimal('0.00')

        # 1) Armar el dict de variantes
        selected = {}
        if self.size:     selected['size']     = self.size
        if self.weight:   selected['weight']   = self.weight
        if self.material: selected['material'] = self.material
        if self.color:    selected['color']    = self.color
        if self.flavor:   selected['flavor']   = self.flavor

        # 2) Delegar en el producto
        price = prod.get_price_with_selected(selected)

        # 3) Asegurar dos decimales
        return price.quantize(Decimal('0.01'))

    @property
    def base_total(self) -> Decimal:
        return (self.unit_price() * self.count).quantize(Decimal('0.01'))

    @property
    def discount_amount(self) -> Decimal:
        if not self.coupon:
            return Decimal('0.00')
        return self.coupon.apply_item_discount(self.unit_price(), self.count)

    @property
    def total_price(self) -> Decimal:
        return (self.base_total - self.discount_amount).quantize(Decimal('0.01'))
