from pprint import pprint
from faker import Faker
import random
import uuid
from datetime import timedelta

from rest_framework_api.views import StandardAPIView
from rest_framework.exceptions import NotFound, APIException, ValidationError
from rest_framework import permissions, status
from django.db import transaction
from django.conf import settings
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django.db.models import DecimalField, FloatField, IntegerField
from django.db.models import Q, F, Prefetch, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
import redis
from bs4 import BeautifulSoup

from core.permissions import HasValidAPIKey
from .models import (Product, ProductInteraction, ProductAnalytics,Category, CategoryInteraction, CategoryAnalytics)
from .serializers import (ProductSerializer, ProductListSerializer, CategorySerializer)
from apps.assets.models import Media
from utils.ip_utils import get_client_ip, get_device_type

redis_client = redis.StrictRedis(host=settings.REDIS_HOST, port=6379, db=0)



class ListProductView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    SORTING_OPTIONS = {
        "views": "analytics_views",
        "likes": "analytics_likes",
        "shares": "analytics_shares",
        "wishlist": "analytics_wishlist",
        "purchases": "analytics_purchases",
        "revenue": "analytics_revenue",
        "rating": "analytics_avg_rating",
        "created_at": "created_at",
        "price": "price",
    }

    @method_decorator(cache_page(60 * 1))
    def get(self, request):
        """
        Enlistar los productos, aplicando filtros, búsqueda y ordenamiento.
        La respuesta se cachea durante 1 minuto.
        """

        try:
            # --- 1) Parámetros de la petición ---
            search      = request.query_params.get("search", "").strip()
            sorting     = request.query_params.get("sorting")
            ordering    = request.query_params.get("ordering", "desc").lower()
            categories  = request.query_params.getlist("categories", [])
            
            # --- 2) Queryset base y optimización de columnas ---
            qs = Product.postobjects.all()

            # --- 3) Limitar columnas (las que serializas explícitamente) ---
            qs = qs.only(
                # tus campos actuales…
                'id', 'author',
                'title', 'short_description',
                'slug',
                'price', 'compare_price', 'discount', 'discount_until',
                'stock', 'limited_edition', 'condition',
                # campos FK necesarios para select_related:
                'category__id',
                'sub_category__id',
                'topic__id',
                'product_analytics__id',
            ).select_related(
                'category',
                'sub_category',
                'topic',
                'product_analytics',
            )

            # --- 4) Anotaciones necesarias para ratings y conteo de reviews ---
            qs = qs.annotate(
                analytics_avg_rating=Coalesce(
                    F('product_analytics__average_rating'),
                    Value(0), output_field=FloatField()
                ),
                analytics_review_count=Coalesce(
                    F('product_analytics__review_count'),
                    Value(0), output_field=IntegerField()
                ),
            )

            # --- 5) Filtro de búsqueda libre ---
            if search:
                qs = qs.filter(
                    Q(title__icontains=search) |
                    Q(short_description__icontains=search) |
                    Q(description__icontains=search) |
                    Q(slug__icontains=search) |
                    Q(keywords__icontains=search)
                )

            # --- 6) Filtro por categorías, subcategoría o tema ---
            if categories:
                q_filters = Q()
                for identifier in categories:
                    try:
                        # Si es UUID, filtramos por los tres campos
                        uuid_val = uuid.UUID(identifier)
                        q_filters |= Q(category__id=uuid_val)
                        q_filters |= Q(sub_category__id=uuid_val)
                        q_filters |= Q(topic__id=uuid_val)
                    except ValueError:
                        # Si no es UUID, lo tratamos como slug
                        q_filters |= Q(category__slug=identifier)
                        q_filters |= Q(sub_category__slug=identifier)
                        q_filters |= Q(topic__slug=identifier)
                qs = qs.filter(q_filters)
            
            # --- 7) Ordenamiento si se especifica ---
            if sorting in self.SORTING_OPTIONS:
                sort_field = self.SORTING_OPTIONS[sorting]
                qs = qs.order_by(sort_field if ordering == "asc" else f"-{sort_field}")

            # --- 8) Serialización y paginación ---
            serialized_products = ProductListSerializer(qs, many=True).data
            return self.paginate(request, serialized_products)
            
        except NotFound as e:
            # En caso de no encontrar nada, devolvemos 404 con lista vacía
            return self.response([], status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            # Cualquier otro error levanta un APIException
            raise APIException(detail=f"An unexpected error occurred: {str(e)}")
        

@method_decorator(cache_page(60 * 1), name='dispatch')
class DetailProductView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request):
        """
        Devuelve los datos anotados de un producto. El registro
        de la interacción de vista lo maneja el middleware.
        """

        slug = request.query_params.get("slug")
        if not slug:
            raise NotFound(detail="A valid slug must be provided")
        
        # try:
        # 1) Construimos el queryset con el annotate
        qs = Product.objects \
            .annotate(
                analytics_views       = Coalesce(F("product_analytics__views"), Value(0), output_field=IntegerField()),
                analytics_likes       = Coalesce(F("product_analytics__likes"), Value(0), output_field=IntegerField()),
                analytics_shares      = Coalesce(F("product_analytics__shares"), Value(0), output_field=IntegerField()),
                analytics_wishlist    = Coalesce(F("product_analytics__wishlist_count"), Value(0), output_field=IntegerField()),
                analytics_add_to_cart = Coalesce(F("product_analytics__add_to_cart_count"), Value(0), output_field=IntegerField()),
                analytics_purchases   = Coalesce(F("product_analytics__purchases"), Value(0), output_field=IntegerField()),
                analytics_revenue     = Coalesce(
                                            F("product_analytics__revenue_generated"),
                                            Value(0),
                                            output_field=DecimalField(max_digits=10, decimal_places=2),
                                        ),
                analytics_avg_rating  = Coalesce(F("product_analytics__average_rating"), Value(0), output_field=FloatField()),
                analytics_review_count= Coalesce(F("product_analytics__review_count"), Value(0), output_field=IntegerField()),
            ) \
            .select_related(   # para FKs únicos
                "category",
                "sub_category",
                "topic",
                "thumbnail",
            ) \
            .prefetch_related( # para M2M y relaciones inversas
                "images",
                "colors",
                "sizes",
                "materials",
                "weights",
                "flavors",
                "details",
                "requisites",
                "benefits",
                "target_audience",
            )

        # 2) Obtenemos el objeto anotado
        product = get_object_or_404(qs, slug=slug)

        # 3) Serializamos
        serialized_product = ProductSerializer(product, context={'request': request}).data

        # except Product.DoesNotExist:
        #     raise NotFound(detail="The requested product does not exist")
        # except Exception as e:
        #     raise APIException(detail=f"An unexpected error occurred: {str(e)}")

        return self.response(serialized_product)


class ProductStockView(StandardAPIView):
    permission_classes = [HasValidAPIKey]  # igual que tus vistas

    def get(self, request):
        """
        Devuelve únicamente el stock actual del producto indicado por slug.
        No se cachea para tener siempre datos frescos.
        """
        slug = request.query_params.get("slug")
        if not slug:
            raise NotFound(detail="Debe proporcionar un slug válido")

        product = get_object_or_404(Product, slug=slug)
        return self.response(product.total_stock)


class ProductPriceView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request):
        slug = request.query_params.get("slug")
        if not slug:
            raise NotFound(detail="Debe proporcionar un slug válido")

        product = get_object_or_404(Product, slug=slug)

        # 1) Recogemos atributos válidos
        selected = {}
        for param, rel in (
            ("color_id", "colors"),
            ("size_id", "sizes"),
            ("material_id", "materials"),
            ("weight_id", "weights"),
            ("flavor_id", "flavors"),
        ):
            raw = request.query_params.get(param)
            if raw and raw.lower() != "null":
                try:
                    uuid_val = uuid.UUID(raw)
                    selected[param] = getattr(product, rel).get(pk=uuid_val)
                except (ValueError, getattr(product, rel).model.DoesNotExist):
                    continue

        # 2) Precio base (producto.price) + atributos
        price_with_attrs = product.get_price_with_selected(selected)

        # 3) Precio antiguo + atributos
        compare_base = product.compare_price or 0
        attrs_extra = sum((attr.price or 0) for attr in selected.values())
        old_price_with_attrs = compare_base + attrs_extra

        # 4) Determinamos si el descuento está activo
        now = timezone.now()
        is_on_discount = (
            product.discount
            and product.compare_price is not None
            and product.discount_until
            and now < product.discount_until
        )

        # 5) Construimos la respuesta
        data = {
            "price": price_with_attrs,
            # Sólo enviamos compare_price si hay descuento activo
            "compare_price": old_price_with_attrs if is_on_discount else None,
        }
        return self.response(data)
    

class UpdateProductAnalyticsView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def post(self, request):
        """
        Incrementa la métrica indicada para el producto especificado.
        """

        slug = request.data.get("slug")
        metric = request.data.get("metric")
        amount = request.data.get("amount", 1)

        if not slug or not metric:
            raise ValidationError("Both 'slug' and 'metric' are required fields.")
        
        try:
            product = Product.objects.get(slug=slug)
        except Product.DoesNotExist:
            raise NotFound(f"No product found with slug '{slug}'.")
        
        try:
            analytics, _ = ProductAnalytics.objects.get_or_create(product=product)
            analytics.increment_metric(metric, amount)

            return self.response(f"Metric '{metric}' incremented by {amount}.")

        except ValueError as e:
            raise ValidationError(str(e))
        except Exception as e:
            raise APIException(f"An error occurred: {str(e)}")
        

class GenerateFakeProductsView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def post(self, request):
        """
        Genera productos falsos en bulk.
        """
        count = int(request.data.get("count", 10))
        faker = Faker()

        # Obtener algunas imágenes válidas para usar como thumbnails/imágenes
        media_images = list(Media.objects.filter(media_type="image"))

        if not media_images:
            return self.response({"error": "No hay imágenes disponibles para asignar a productos."},
                            status=status.HTTP_400_BAD_REQUEST)

        created = []

        for _ in range(count):
            title = faker.sentence(nb_words=4)
            slug = slugify(title)

            product = Product.objects.create(
                author="ac68ca5f-07fe-4906-be85-cb5e1da6b8fb",
                title=title,
                short_description=faker.sentence(),
                description=faker.text(max_nb_chars=300),
                keywords=", ".join(faker.words(5)),
                slug=slug,
                thumbnail=random.choice(media_images),
                price=round(random.uniform(2, 100), 2),
                compare_price=round(random.uniform(100, 150), 2),
                discount=random.choice([True, False]),
                discount_until=timezone.now() + timezone.timedelta(days=random.randint(1, 30)),
                stock=random.randint(0, 100),
                hidden=False,
                banned=False,
                can_delete=True,
                limited_edition=random.choice([True, False]),
                condition=random.choice(["new", "used", "broken"]),
                packaging=random.choice(["normal", "gift"]),
                status=random.choice(["draft", "published"]),
            )

            # Asociar 1-3 imágenes adicionales
            images_to_add = random.sample(media_images, k=min(len(media_images), random.randint(1, 3)))
            product.images.set(images_to_add)

            created.append(product.slug)

        return self.response(
            {"message": f"Se generaron {count} productos de prueba.", "slugs": created},
            status=status.HTTP_201_CREATED
        )
    

class ToggleLikeView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def post(self, request):
        product_id = request.data.get("product_id")
        if not product_id:
            return self.error("Product ID is required.")

        product = get_object_or_404(Product, id=product_id)

        user = request.user if request.user.is_authenticated else None
        session_id = request.session.session_key

        if not session_id:
            request.session.save()
            session_id = request.session.session_key

        like_filter = {
            "product": product,
            "interaction_type": "like"
        }

        if user:
            like_filter["user"] = user
        else:
            like_filter["session_id"] = session_id

        existing_like = ProductInteraction.objects.filter(**like_filter).first()

        analytics, _ = ProductAnalytics.objects.get_or_create(product=product)

        if existing_like:
            existing_like.delete()
            analytics.increment_metric("likes", amount=-1)
            return self.response({"liked": False})
        else:
            ProductInteraction.objects.create(
                user=user,
                session_id=session_id,
                product=product,
                interaction_type="like",
                ip_address=get_client_ip(request),
                device_type=get_device_type(request),
                weight=1.0,
            )
            # analytics.increment_metric("likes", amount=1)
            return self.response({"liked": True}, status=status.HTTP_201_CREATED)
        

class RegisterShareView(StandardAPIView):
    permission_classes = [HasValidAPIKey]
    
    def post(self, request):
        product_id = request.data.get("product_id")
        if not product_id:
            return self.error("Product ID is required.")

        product = get_object_or_404(Product, id=product_id)

        user = request.user if request.user.is_authenticated else None
        session_id = request.session.session_key
        if not session_id:
            request.session.save()
            session_id = request.session.session_key

        ip_address = get_client_ip(request)
        device_type = get_device_type(request)

        # Registrar la interacción
        ProductInteraction.objects.create(
            product=product,
            user=user,
            session_id=session_id,
            interaction_type="share",
            ip_address=ip_address,
            device_type=device_type,
            weight=1.0
        )

        # La señal post_save se encargará de actualizar analytics.shares += 1

        return self.response("Share registrado", status=status.HTTP_201_CREATED)
    

class CategoryListView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    @method_decorator(cache_page(60 * 1))
    def get(self, request):
        """
        Lista categorías (filtrado por nivel, búsqueda, ordenamiento y flag 'all').
        La respuesta se cachea 5 minutos y las impresiones se cuentan en middleware.
        """

        try:
            # 1) Parámetros
            parent_slug = request.query_params.get("parent_slug")
            ordering    = request.query_params.get("ordering")
            sorting     = request.query_params.get("sorting")
            search      = request.query_params.get("search", "").strip()
            all_flag    = request.query_params.get("all", "false").lower() == "true"

            # 2) Queryset base: analytics en JOIN + prefetch de hijos
            qs = Category.objects.select_related("category_analytics") \
                                 .prefetch_related("children")

            # 3) Filtrar por nivel (raíz o un parent concreto)
            if not all_flag:
                if parent_slug:
                    qs = qs.filter(parent__slug=parent_slug)
                else:
                    qs = qs.filter(parent__isnull=True)
            
            # 4) Filtrar por texto libre
            if search:
                qs = qs.filter(
                    Q(name__icontains=search) |
                    Q(slug__icontains=search) |
                    Q(title__icontains=search) |
                    Q(description__icontains=search)
                )
            
            # 5) Ordenamiento por fecha o vistas
            if sorting:
                if sorting == "newest":
                    qs = qs.order_by("-created_at")
                elif sorting == "recently_updated":
                    qs = qs.order_by("-updated_at")
                elif sorting == "most_viewed":
                    # annotate sólo para ordenar
                    qs = qs.annotate(
                        popularity=Coalesce(
                            F("category_analytics__views"),
                            Value(0),
                            output_field=IntegerField()
                        )
                    ).order_by("-popularity")

            # 6) Orden alfabético
            if ordering:
                qs = qs.order_by("name" if ordering == "az" else "-name")

            # 7) Validación de existencia
            if not qs.exists():
                raise NotFound("No categories found.")

            # 8) Serialización y paginación
            data = CategorySerializer(qs, many=True).data
            return self.paginate(request, data)
        except NotFound as e:
            return self.response([], status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            raise APIException(detail=f"An unexpected error occurred: {str(e)}")
        

class UpdateCategoryAnalyticsView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def post(self, request):
        """
        Incrementa la métrica indicada para la categoria especificado.
        """

        slug = request.data.get("slug")
        metric = request.data.get("metric")
        amount = request.data.get("amount", 1)

        if not slug or not metric:
            raise ValidationError("Both 'slug' and 'metric' are required fields.")
        
        try:
            category = Category.objects.get(slug=slug)
        except Category.DoesNotExist:
            raise NotFound(f"No category found with slug '{slug}'.")
        
        try:
            analytics, _ = CategoryAnalytics.objects.get_or_create(category=category)
            analytics.increment_metric(metric, amount)

            return self.response(f"Metric '{metric}' incremented by {amount}.")

        except ValueError as e:
            raise ValidationError(str(e))
        except Exception as e:
            raise APIException(f"An error occurred: {str(e)}")
  

class AutoCategorizeProducts(StandardAPIView):
    """
    Recorre todos los productos sin categoría y trata de asignar
    category, sub_category y topic buscando coincidencias
    en title/keywords/description.
    """
    def post(self, request):
        # 1) Obtener la primera categoría raíz (sin parent)
        root = Category.objects.filter(parent__isnull=True).order_by('name').first()
        if not root:
            return self.response(
                {"detail": "No se encontró ninguna categoría raíz."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 2) Obtener la primera sub-categoría de esa raíz
        sub = Category.objects.filter(parent=root).order_by('name').first()
        if not sub:
            return self.response(
                {"detail": f"No se encontró sub-category para {root.name}."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 3) Obtener el primer topic de esa sub-categoría
        topic = Category.objects.filter(parent=sub).order_by('name').first()
        if not topic:
            return self.response(
                {"detail": f"No se encontró topic para {sub.name}."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 4) Asignar a productos huérfanos
        to_assign = Product.objects.filter(category__isnull=True)
        assigned = []

        with transaction.atomic():
            for prod in to_assign:
                prod.category     = root
                prod.sub_category = sub
                prod.topic        = topic
                prod.save(update_fields=['category', 'sub_category', 'topic'])
                assigned.append(str(prod.id))

        return self.response({
            "assigned_count": len(assigned),
            "category": root.slug,
            "sub_category": sub.slug,
            "topic": topic.slug,
            "products": assigned
        }, status=status.HTTP_200_OK)
    

@method_decorator(cache_page(60), name='dispatch')
class DetailCategoryView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    
    def get(self, request):
        """
        Devuelve datos anotados de una categoría; la interacción de 'view'
        se registra en middleware.
        """

        slug = request.query_params.get("slug")
        if not slug:
            raise NotFound(detail="A valid slug must be provided")

        # 1) Construir queryset con sólo las anotaciones que usamos
        qs = Category.objects.annotate(
            analytics_views=Coalesce(
                F("category_analytics__views"), Value(0), output_field=IntegerField()
            ),
            analytics_likes=Coalesce(
                F("category_analytics__likes"), Value(0), output_field=IntegerField()
            ),
            analytics_shares=Coalesce(
                F("category_analytics__shares"), Value(0), output_field=IntegerField()
            ),
            analytics_wishlist=Coalesce(
                F("category_analytics__wishlist_count"), Value(0), output_field=IntegerField()
            ),
            analytics_add_to_cart=Coalesce(
                F("category_analytics__add_to_cart_count"), Value(0), output_field=IntegerField()
            ),
            analytics_purchases=Coalesce(
                F("category_analytics__purchases"), Value(0), output_field=IntegerField()
            ),
            analytics_revenue=Coalesce(
                F("category_analytics__revenue_generated"),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )

        # 2) Recuperar o404
        category = get_object_or_404(qs, slug=slug)

        # 3) Serializar y devolver
        data = CategorySerializer(category, context={"request": request}).data
        return self.response(data)
    

class ListProductsByIdView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request):
        # 1) Obtengo la lista de IDs de los params
        raw_ids = request.query_params.getlist("product_ids")
        if not raw_ids:
            raise ValidationError(
                "Debes pasar al menos un parámetro 'product_ids', ej: "
                "?product_ids=uuid1&product_ids=uuid2"
            )

        # 2) Valido que sean UUIDs
        try:
            uuids = [uuid.UUID(pid) for pid in raw_ids]
        except ValueError:
            raise ValidationError("Todos los valores de 'product_ids' deben ser UUIDs válidos.")

        # 3) Construyo el queryset
        qs = (
            Product.postobjects
            .filter(id__in=uuids)
            .only(
                "id", "author",
                "title", "short_description", "slug",
                "price", "compare_price", "discount", "discount_until",
                "stock", "limited_edition", "condition"
            )
        )

        # 4) Serializo y retorno
        serialized = ProductListSerializer(qs, many=True).data
        return self.response(serialized, status=200)


class ListProductsFromCartItemByIdView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request):
        # 1) IDs de productos
        raw_ids = request.query_params.getlist('product_ids')
        if not raw_ids:
            raise ValidationError(
                "Debes pasar al menos un parámetro 'product_ids', ej: ?product_ids=uuid1&product_ids=uuid2"
            )
        try:
            product_uuids = [uuid.UUID(pid) for pid in raw_ids]
        except ValueError:
            raise ValidationError("Todos los valores de 'product_ids' deben ser UUIDs válidos.")

        # 2) IDs de atributos paralelos (misma posición que product_ids)
        color_ids    = request.query_params.getlist('color_id')
        size_ids     = request.query_params.getlist('size_id')
        material_ids = request.query_params.getlist('material_id')
        weight_ids   = request.query_params.getlist('weight_id')
        flavor_ids   = request.query_params.getlist('flavor_id')
        counts       = request.query_params.getlist('count')

        # 3) Queryset de productos
        products = Product.postobjects.filter(id__in=product_uuids)
        serialized = ProductListSerializer(products, many=True).data

        # 4) Empaquetar respuesta por item
        response_items = []
        for idx, prod_data in enumerate(serialized):
            prod_id = uuid.UUID(prod_data['id'])
            product = products.get(id=prod_id)

            # construir selected dict
            selected = {}
            # helper zip param lists
            attr_map = [
                (color_ids,    'colors',    'color_id'),
                (size_ids,     'sizes',     'size_id'),
                (material_ids, 'materials', 'material_id'),
                (weight_ids,   'weights',   'weight_id'),
                (flavor_ids,   'flavors',   'flavor_id'),
            ]
            for id_list, rel, key in attr_map:
                if idx < len(id_list):
                    raw = id_list[idx]
                    if raw and raw.lower() != 'null':
                        try:
                            uuid_val = uuid.UUID(raw)
                            selected[key] = getattr(product, rel).get(pk=uuid_val)
                        except (ValueError, getattr(product, rel).model.DoesNotExist):
                            pass

            # 5) precio unitario con atributos
            unit_price = product.get_price_with_selected(selected)

            # 6) cantidad
            count = 1
            if idx < len(counts):
                try:
                    count = int(counts[idx])
                except ValueError:
                    count = 1

            # 7) precio total
            total_price = unit_price * count

            response_items.append({
                'product': prod_data,
                'selected': {k: str(v.id) for k, v in selected.items()},
                'unit_price': unit_price,
                'count': count,
                'total_price': total_price,
            })

        return self.response(response_items, status=200)