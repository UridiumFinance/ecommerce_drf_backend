import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey

from apps.cart.models import ShippingMethod, Coupon
from apps.addresses.models import ShippingAddress

class Order(models.Model):
    PENDING   = 'pending'
    PAID      = 'paid'
    SHIPPED   = 'shipped'
    DELIVERED = 'delivered'
    CANCELED  = 'canceled'


    STATUS_CHOICES = [
        (PENDING,   'Pendiente de pago'),
        (PAID,      'Pagada'),
        (SHIPPED,   'Enviada'),
        (DELIVERED, 'Entregada'),
        (CANCELED,  'Cancelada'),
    ]

    id                = models.UUIDField(primary_key=True,
                                         default=uuid.uuid4,
                                         editable=False)
    user              = models.ForeignKey(settings.AUTH_USER_MODEL,
                                          on_delete=models.PROTECT,
                                          related_name='orders')
    shipping_address  = models.ForeignKey(ShippingAddress,
                                          on_delete=models.SET_NULL,
                                          null=True,
                                          blank=True)
    shipping_method   = models.ForeignKey(ShippingMethod,
                                          on_delete=models.SET_NULL,
                                          null=True,
                                          blank=True)
    shipping_cost     = models.DecimalField(max_digits=8,
                                            decimal_places=2,
                                            default=Decimal('0.00'))
    coupon            = models.ForeignKey(Coupon,
                                          null=True,
                                          blank=True,
                                          on_delete=models.SET_NULL)
    subtotal          = models.DecimalField(max_digits=10,
                                            decimal_places=2,
                                            help_text="Sin descuentos ni envío")
    items_discount    = models.DecimalField(max_digits=10,
                                            decimal_places=2,
                                            default=Decimal('0.00'),
                                            help_text="Descuento total por ítems")
    global_discount   = models.DecimalField(max_digits=10,
                                            decimal_places=2,
                                            default=Decimal('0.00'),
                                            help_text="Descuento global del cupón")
    tax_amount        = models.DecimalField(max_digits=10,
                                            decimal_places=2,
                                            default=Decimal('0.00'))
    total             = models.DecimalField(max_digits=10,
                                            decimal_places=2,
                                            help_text="Total final a pagar")
    status            = models.CharField(max_length=20,
                                         choices=STATUS_CHOICES,
                                         default=PENDING)
    payment_reference = models.CharField(max_length=255,
                                         blank=True,
                                         help_text="ID de la pasarela de pago")
    
    tracking_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Número de seguimiento proporcionado por el transportista"
    )
    tracking_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL para rastrear el envío en el sitio del transportista"
    )

    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Order {self.id} ({self.get_status_display()})"


class OrderItem(models.Model):
    """
    Copia de CartItem para mantener histórico de variantes y precios.
    """
    id              = models.UUIDField(primary_key=True,
                                       default=uuid.uuid4,
                                       editable=False)
    order           = models.ForeignKey(Order,
                                        on_delete=models.CASCADE,
                                        related_name='items')
    # Información inmutable de producto/curso
    content_type    = models.ForeignKey('contenttypes.ContentType',
                                        on_delete=models.PROTECT)
    object_id       = models.UUIDField()
    item_name       = models.CharField(max_length=255)

    item            = GenericForeignKey('content_type', 'object_id')
    
    unit_price      = models.DecimalField(max_digits=10,
                                          decimal_places=2)
    quantity        = models.PositiveIntegerField(default=1)
    item_discount   = models.DecimalField(max_digits=10,
                                          decimal_places=2,
                                          default=Decimal('0.00'))
    total_price     = models.DecimalField(max_digits=10,
                                          decimal_places=2,
                                          help_text="(unit_price * quantity) - item_discount")
    # Snapshot de variantes (opcionales)
    size_title      = models.CharField(max_length=100, blank=True)
    weight_title    = models.CharField(max_length=100, blank=True)
    material_title  = models.CharField(max_length=100, blank=True)
    color_title     = models.CharField(max_length=100, blank=True)
    flavor_title    = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['order', 'item_name']
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f"{self.quantity}× {self.item_name} — Order {self.order.id}"