from celery import shared_task

import logging

import redis
from django.conf import settings

from .models import ProductAnalytics, Product, Category, CategoryAnalytics

logger = logging.getLogger(__name__)

redis_client = redis.StrictRedis(host=settings.REDIS_HOST, port=6379, db=0)


@shared_task
def increment_product_impressions(product_id):
    """
    Incrementa las impresiones del post asociado
    """
    try:
        analytics, created = ProductAnalytics.objects.get_or_create(product__id=product_id)
        analytics.increment_impression()
    except Exception as e:
        logger.info(f"Error incrementing impressions for Product ID {product_id}: {str(e)}")

@shared_task
def sync_product_impressions_to_db():
    """
    Sincronizar las impresiones almacenadas en redis con la base de datos
    """
    keys = redis_client.keys("product:impressions:*")
    for key in keys:
        try:
            product_id = key.decode("utf-8").split(":")[-1]

            # Validar que el producto existe
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                logger.info(f"Product with ID {product_id} does not exist. Skipping.")
                continue

            # Obtener impresiones de redis
            impressions = int(redis_client.get(key))
            if impressions == 0:
                redis_client.delete(key)
                continue
            
            # Obtener y crear instancia de Product analytics
            analytics, created = ProductAnalytics.objects.get_or_create(product=product)

            # Incrementar impresiones
            analytics.impressions += impressions
            analytics.save()

            # Incrementar la tasa de clics (CTR)
            analytics._update_click_through_rate()

            # Eliminar la clave de redis despues de sincronizar
            redis_client.delete(key)
        except Exception as e:
            print(f"Error syncing impressions for {key}: {str(e)}")


@shared_task
def sync_category_impressions_to_db():
    """
    Sincronizar las impresiones almacenadas en redis con la base de datos
    """
    keys = redis_client.keys("category:impressions:*")
    for key in keys:
        try:
            category_id = key.decode("utf-8").split(":")[-1]

            # Validar que el producto existe
            try:
                category = Category.objects.get(id=category_id)
            except Product.DoesNotExist:
                logger.info(f"Category with ID {category_id} does not exist. Skipping.")
                continue

            # Obtener impresiones de redis
            impressions = int(redis_client.get(key))
            if impressions == 0:
                redis_client.delete(key)
                continue
            
            # Obtener y crear instancia de Product analytics
            analytics, created = CategoryAnalytics.objects.get_or_create(category=category)

            # Incrementar impresiones
            analytics.impressions += impressions
            analytics.save()

            # Incrementar la tasa de clics (CTR)
            analytics._update_click_through_rate()

            # Eliminar la clave de redis despues de sincronizar
            redis_client.delete(key)
        except Exception as e:
            print(f"Error syncing impressions for {key}: {str(e)}")