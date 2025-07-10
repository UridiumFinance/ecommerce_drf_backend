import logging
import json
from datetime import timedelta
from uuid import UUID

import redis
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from rest_framework.exceptions import APIException
from django.shortcuts import get_object_or_404

from .models import Product, ProductInteraction, Category, CategoryInteraction
from utils.ip_utils import get_client_ip, get_device_type

logger = logging.getLogger(__name__)

redis_client = redis.StrictRedis(
    host=settings.REDIS_HOST,
    port=6379,
    db=0,
    decode_responses=True,
)

class ImpressionMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if (
            request.method == "GET"
            and request.path.startswith("/api/products/list/")
            and response.status_code == 200
            and response.get("Content-Type", "").startswith("application/json")
        ):
            try:
                payload = json.loads(response.content)
                items = payload.get("results") or payload.get("data") or []
                ids = [item.get("id") for item in items if item.get("id")]
                if ids:
                    pipe = redis_client.pipeline()
                    for pid in ids:
                        pipe.incr(f"product:impressions:{pid}")
                    pipe.execute()
                    logger.info("ImpressionMiddleware: incremented impressions for %d products", len(ids))
            except Exception as e:
                logger.warning("ImpressionMiddleware error parsing response: %s", e)
        return response

class IncrementViewCountMiddleware(MiddlewareMixin):
    """
    Registra una interacción de vista solo en el endpoint de detalle,
    ignorando precio y stock para evitar múltiples llamadas.
    Bloquea anomalías sin tumbar la respuesta.
    """
    def process_response(self, request, response):
        path = request.path.lower()
        # solo detalle, no price ni stock
        if (
            request.method == "GET"
            and path.startswith("/api/products/detail/")
            and not path.startswith("/api/products/detail/price/")
            and not path.startswith("/api/products/detail/stock/")
            and response.status_code == 200
        ):
            slug = request.GET.get("slug")
            if slug:
                try:
                    product = get_object_or_404(Product, slug=slug)
                    now = timezone.now()
                    cutoff = now - timedelta(hours=6)
                    if request.user.is_authenticated:
                        already = ProductInteraction.objects.filter(
                            user=request.user,
                            product=product,
                            interaction_type="view",
                            timestamp__gte=cutoff
                        ).exists()
                        user_obj = request.user
                        session_id = None
                    else:
                        session_id = request.session.session_key or request.session.save() or request.session.session_key
                        ip = get_client_ip(request)
                        already = ProductInteraction.objects.filter(
                            product=product,
                            interaction_type="view",
                            session_id=session_id,
                            ip_address=ip,
                            timestamp__gte=cutoff
                        ).exists()
                        user_obj = None

                    if not already:
                        try:
                            ProductInteraction.objects.create(
                                user=user_obj,
                                session_id=session_id,
                                product=product,
                                interaction_type="view",
                                ip_address=get_client_ip(request),
                                device_type=get_device_type(request),
                                weight=1.0,
                            )
                            logger.info("Registered view interaction for product %s", slug)
                        except ValueError:
                            # anomalía detectada: ignorar sin romper
                            logger.info("Anomalous interaction blocked for product %s", slug)
                        except Exception as e:
                            logger.warning("Error registering view interaction: %s", e)
                except Exception as e:
                    logger.warning("IncrementViewCountMiddleware lookup error: %s", e)
        return response

class CategoryListImpressionMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if (
            request.method == "GET"
            and request.path.startswith("/api/products/categories/")
            and response.status_code == 200
            and response.get("Content-Type", "").startswith("application/json")
        ):
            try:
                payload = json.loads(response.content)
                items = payload.get("results", [])
                ids = [item.get("id") for item in items if item.get("id")]
                if ids:
                    pipe = redis_client.pipeline()
                    for cid in ids:
                        pipe.incr(f"category:impressions:{cid}")
                    pipe.execute()
                    logger.info("Contadas impresiones para %d categorías", len(ids))
            except Exception as e:
                logger.warning("Error en CategoryListImpressionMiddleware: %s", e)
        return response

class CategoryDetailImpressionMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        path = request.path.lower()
        if (
            request.method == "GET"
            and path.startswith("/api/products/category/")
            and response.status_code == 200
        ):
            slug = request.GET.get("slug")
            if slug:
                try:
                    category = Category.objects.get(slug=slug)
                    now = timezone.now()
                    cutoff = now - timedelta(hours=6)
                    if request.user.is_authenticated:
                        already = CategoryInteraction.objects.filter(
                            user=request.user,
                            category=category,
                            interaction_type="view",
                            timestamp__gte=cutoff,
                        ).exists()
                        user_obj = request.user
                        session_id = None
                    else:
                        session_id = request.session.session_key or request.session.save() or request.session.session_key
                        ip = get_client_ip(request)
                        already = CategoryInteraction.objects.filter(
                            category=category,
                            interaction_type="view",
                            session_id=session_id,
                            ip_address=ip,
                            timestamp__gte=cutoff,
                        ).exists()
                        user_obj = None

                    if not already:
                        try:
                            CategoryInteraction.objects.create(
                                user=user_obj,
                                session_id=session_id,
                                category=category,
                                interaction_type="view",
                                ip_address=get_client_ip(request),
                                device_type=get_device_type(request),
                                weight=1.0,
                            )
                            logger.info("Registered view for category %s", slug)
                        except Exception as e:
                            logger.warning("Error registering category view: %s", e)
                except Exception as e:
                    logger.warning("CategoryDetailImpressionMiddleware lookup error: %s", e)
        return response
