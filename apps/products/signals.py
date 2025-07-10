import decimal

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Product, ProductAnalytics, ProductInteraction, Category, CategoryInteraction, CategoryAnalytics


@receiver(post_save, sender=Product)
def create_product_analytics(sender, instance, created, **kwargs):
    """
    Crea automáticamente una instancia de ProductAnalytics cuando se crea un nuevo Product.
    """
    if created:
        # Solo crea si es un nuevo producto
        ProductAnalytics.objects.create(product=instance)


@receiver(post_save, sender=Category)
def create_category_analytics(sender, instance, created, **kwargs):
    """
    Crea automáticamente una instancia de ProductAnalytics cuando se crea un nuevo Product.
    """
    if created:
        # Solo crea si es un nuevo producto
        CategoryAnalytics.objects.create(category=instance)


@receiver(post_save, sender=CategoryInteraction)
def update_category_analytics(sender, instance, created, **kwargs):
    """
    Signal que se activa cuando se guarda una nueva interacción en CategoryInteraction.
    Actualiza el modelo CategoryAnalytics asociado a la categoria.
    """
    if not created:
        return  # Solo actuamos sobre nuevas interacciones
    
    # Obtener o crear el objeto de analítica
    analytics, _ = CategoryAnalytics.objects.get_or_create(category=instance.category)
    now = timezone.now()

    # --- Actualizar métricas según el tipo de interacción ---
    itype = instance.interaction_type

    if itype == "view":
        analytics.views += 1
        analytics.last_viewed_at = now
        if analytics.first_viewed_at is None:
            analytics.first_viewed_at = now

    elif itype == "like":
        analytics.likes += 1

    elif itype == "share":
        analytics.shares += 1

    elif itype == "wishlist":
        analytics.wishlist_count += 1

    elif itype == "add_to_cart":
        analytics.add_to_cart_count += 1

    elif itype == "purchase":
        # Suponemos que en metadata hay 'quantity' y 'total_price'
        qty = instance.metadata.get("quantity", 1) if instance.metadata else 1
        total_price = instance.metadata.get("total_price", 0) if instance.metadata else 0

        analytics.purchases += qty
        analytics.revenue_generated += total_price
        
    # Guardar cambios en campos básicos
    analytics.save(update_fields=[
        "views", "last_viewed_at", "first_viewed_at",
        "likes", "shares", "wishlist_count",
        "add_to_cart_count", "purchases", "revenue_generated",
    ])

    # --- Recalcular métricas derivadas ---
    analytics._update_click_through_rate()
    analytics._update_conversion_rate()
    analytics._update_avg_order_value()


@receiver(post_save, sender=ProductInteraction)
def update_product_analytics(sender, instance, created, **kwargs):
    """
    Signal que se activa cuando se guarda una nueva interacción en ProductInteraction.
    Actualiza el modelo ProductAnalytics asociado al producto.
    """
    if not created:
        return  # Solo actuamos sobre nuevas interacciones
    
    product = instance.product

    # Obtener o crear objeto de analítica para el producto
    analytics, _ = ProductAnalytics.objects.get_or_create(product=product)

    # --- Actualizar métricas específicas según el tipo de interacción ---
    if instance.interaction_type == "view":
        analytics.views += 1
        analytics.last_viewed_at = timezone.now()
        if not analytics.first_viewed_at:
            analytics.first_viewed_at = timezone.now()
    
    elif instance.interaction_type == "like":
        analytics.likes += 1

    elif instance.interaction_type == "share":
        analytics.shares += 1

    elif instance.interaction_type == "wishlist":
        analytics.wishlist_count += 1

    elif instance.interaction_type == "add_to_cart":
        analytics.add_to_cart_count += 1

    elif instance.interaction_type == "remove_from_cart":
        analytics.remove_from_cart_count += 1

    elif instance.interaction_type == "purchase":
        analytics.purchases += 1

        # Acumular ingresos
        if instance.total_price:
            analytics.revenue_generated += instance.total_price

        # Recalcular promedio de orden
        if analytics.purchases > 0:
            analytics.avg_order_value = analytics.revenue_generated / decimal.Decimal(analytics.purchases)

    elif instance.interaction_type == "rate":
        # Recalcular promedio de rating
        existing = analytics.review_count
        new_rating = instance.rating or 0
        if new_rating:
            total_rating = (analytics.average_rating * existing) + new_rating
            analytics.review_count += 1
            analytics.average_rating = total_rating / analytics.review_count

    # --- Recalcular métricas derivadas ---
    if analytics.impressions > 0:
        analytics.click_through_rate = (analytics.clicks / analytics.impressions) * 100

    if analytics.add_to_cart_count > 0:
        abandoned = analytics.add_to_cart_count - analytics.purchases
        analytics.cart_abandonment_rate = (abandoned / analytics.add_to_cart_count) * 100

    if analytics.views > 0:
        analytics.conversion_rate = (analytics.purchases / analytics.views) * 100

    # Guardar cambios
    analytics.save()
