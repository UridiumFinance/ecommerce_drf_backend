from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework_api.views import StandardAPIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.conf import settings

from utils.ip_utils import get_client_ip, get_device_type

from django.contrib.contenttypes.models import ContentType
from apps.products.models import ProductInteraction
from apps.addresses.models import ShippingAddress

from .models import Cart, CartItem, Coupon, ShippingZone, ShippingMethod
from .serializers import CartSerializer, CartItemSerializer, ShippingMethodSerializer
from .utils import add_to_cart_generic
from core.permissions import HasValidAPIKey


class ListCartView(StandardAPIView):
    """
    GET /cart/

    Parámetros opcionales por query string:
      - coupon_code=<string>: código de cupón a aplicar o '' para remover.
      - shipping_address_id=<uuid>: ID de dirección para asignar al carrito.
      - shipping_method_id=<uuid>: ID de método de envío para asignar.

    Respuesta 200:
    {
      "id": <uuid>,
      "user": <usuario>,
      "items": [...],
      "total_items": <int>,
      "subtotal": <decimal>,
      "items_discount": <decimal>,
      "cart_discount": <decimal>,
      "discount_amount": <decimal>,
      "tax_amount": <decimal>,
      "delivery_fee": <decimal>,
      "total": <decimal>,
      "shipping_address": {...},
      "shipping_method": {...},
      "shipping_cost": <decimal>,
      "coupon": <string|null>
    }
    """
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        cart, _ = Cart.objects.prefetch_related(
            'items__item', 'items__size', 'items__weight',
            'items__material', 'items__color', 'items__flavor'
        ).get_or_create(user=request.user.id)

        coupon_code       = request.query_params.get('coupon_code')
        addr_id           = request.query_params.get('shipping_address_id')
        method_id         = request.query_params.get('shipping_method_id')
        dirty = False

        # Cupón a nivel de carrito
        if coupon_code is not None:
            if coupon_code == '':
                if cart.coupon:
                    cart.coupon = None
                    dirty = True
            else:
                try:
                    cp = Coupon.objects.get(code=coupon_code)
                    if cp.is_active() and cp.can_user_use(request.user):
                        if cart.coupon_id != cp.id:
                            cart.coupon = cp
                            dirty = True
                except Coupon.DoesNotExist:
                    raise ValidationError("Código de cupón inválido o inactivo.")

        # Asignar dirección de envío
        if addr_id:
            try:
                addr = get_object_or_404(
                    ShippingAddress, pk=UUID(addr_id), user=request.user)
            except Exception:
                raise ValidationError("shipping_address_id inválido")
            if cart.shipping_address_id != addr.id:
                cart.shipping_address = addr
                dirty = True

        # Asignar método de envío
        if method_id:
            try:
                method = get_object_or_404(
                    ShippingMethod,
                    pk=int(method_id),        # <-- aquí pasamos int, no UUID
                    active=True
                )
            except (ValueError, ShippingMethod.DoesNotExist):
                raise ValidationError("shipping_method_id inválido")
            # validar que la zona cubre el país
            if cart.shipping_address and \
               cart.shipping_address.country not in method.zone.countries:
                raise ValidationError("Método de envío no disponible para la dirección seleccionada")
            if cart.shipping_method_id != method.id:
                cart.shipping_method = method
                dirty = True

        # Recalcular costos si hubo cambios
        if dirty:
            cart.recalc_shipping()
            cart.save(update_fields=['coupon', 'shipping_address', 'shipping_method'])

        serializer = CartSerializer(cart, context={'request': request})
        return self.response(serializer.data)


class AddCartItemView(StandardAPIView):
    """
    POST /cart/items/

    Body JSON:
      {
        "content_type": "product|course",
        "object_id": "<uuid>",
        "count": <int>,
        "size_id": <int>, "weight_id": <int>, ...,
        "coupon_code": <string>  # opcional, cupón para este ítem
      }

    Respuesta 201: mismo payload que GET /cart/.
    """
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    @transaction.atomic
    def post(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user.id)
        serializer = CartItemSerializer(
            data=request.data,
            context={'cart': cart, 'request': request}
        )
        serializer.is_valid(raise_exception=True)
        ci = serializer.save()

        # Registrar interacción analytics si es producto
        if ci.content_type.model == 'product':
            ProductInteraction.objects.create(
                product=ci.item,
                user=request.user,
                session_id=str(cart.id),
                interaction_type='add_to_cart',
                interaction_category='active',
                quantity=ci.count,
                total_price=ci.total_price,
                ip_address=get_client_ip(request),
                device_type=get_device_type(request),
                hour_of_day=ci.added_at.hour,
                day_of_week=ci.added_at.weekday(),
                metadata={},
            )

        return ListCartView().get(request)


class UpdateCartItemView(StandardAPIView):
    """
    PATCH /cart/items/<cart_item_id>/

    Body JSON (parcial):
      { "count": <int>, "size_id": <int>, ..., "coupon_code": <string> }

    Actualiza cantidad, variantes o cupón de un CartItem. Devuelve GET /cart/.
    """
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    @transaction.atomic
    def patch(self, request, cart_item_id=None):
        if not cart_item_id:
            raise ValidationError("Falta <cart_item_id> en la URL.")
        cart = get_object_or_404(Cart, user=request.user.id)
        ci   = get_object_or_404(CartItem, id=cart_item_id, cart=cart)

        serializer = CartItemSerializer(
            ci,
            data=request.data,
            partial=True,
            context={'cart': cart, 'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return ListCartView().get(request)


class RemoveCartItemView(StandardAPIView):
    """
    DELETE /cart/items/<cart_item_id>/?remove_count=<n>

    Parámetros:
      - remove_count: cantidad a decrementar (>=1). Si no se pasa, elimina todo.

    Registra interacción y devuelve GET /cart/.
    """
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    http_method_names      = ['delete']

    @transaction.atomic
    def delete(self, request, cart_item_id=None):
        if not cart_item_id:
            raise ValidationError("Falta <cart_item_id> en la URL.")
        cart = get_object_or_404(Cart, user=request.user.id)
        ci   = get_object_or_404(CartItem, id=cart_item_id, cart=cart)

        n = int(request.query_params.get('remove_count', ci.count))
        if n < 1:
            raise ValidationError("remove_count debe ser >=1.")

        if ci.content_type.model == 'product':
            ProductInteraction.objects.create(
                product=ci.item,
                user=request.user,
                session_id=str(cart.id),
                interaction_type='remove_from_cart',
                interaction_category='active',
                quantity=n,
                total_price=ci.unit_price() * n,
                ip_address=get_client_ip(request),
                hour_of_day=timezone.now().hour,
                day_of_week=timezone.now().weekday(),
            )

        if ci.count > n:
            ci.count -= n
            ci.save(update_fields=['count'])
        else:
            ci.delete()

        return ListCartView().get(request)


class ClearCartView(StandardAPIView):
    """
    POST /cart/clear/

    Elimina todos los ítems y remueve cupón del carrito.
    Respuesta 200: { "message": "Carrito limpiado." }
    """
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        cart = get_object_or_404(Cart, user=request.user.id)
        cart.items.all().delete()
        cart.coupon = None
        cart.save(update_fields=['coupon'])
        return Response({'message': 'Carrito limpiado.'}, status=status.HTTP_200_OK)


class PreviewCartCalculationView(StandardAPIView):
    """
    POST /cart/preview/

    Cálculo sin login de:
      - precios unitarios antes/después de descuento
      - totales antes/después de item-discount y global-discount
      - impuestos, envío y total final

    Body JSON:
    {
      "items": [
        {"content_type":..., "item_id":..., "count":..., "size_id":..., "coupon_code":...},
        ...
      ],
      "coupon_code": <string>,  # cupón global
      "delivery_fee": <decimal>
    }

    Respuesta 200: { items: [...], subtotal_before, subtotal_after,
                    item_discounts, global_discount, tax_amount,
                    delivery_fee, total }
    """
    permission_classes = [HasValidAPIKey]

    def post(self, request):
        data = request.data
        items = data.get('items')
        if not isinstance(items, list):
            raise ValidationError('Se requiere lista "items".')

        global_code = data.get('coupon_code')
        delivery_fee = Decimal(data.get('delivery_fee', '0'))
        tax_rate = Decimal(settings.TAXES)

        preview = []
        sub_before = sub_after = Decimal('0')

        for itm in items:
            ct = get_object_or_404(ContentType, model=itm.get('content_type'))
            obj = get_object_or_404(ct.model_class(), pk=itm.get('item_id'))
            count = int(itm.get('count', 1))

            # variantes
            selected = {}
            for param, rel in (('size_id','sizes'),('weight_id','weights'),
                               ('material_id','materials'),('color_id','colors'),('flavor_id','flavors')):
                if itm.get(param):
                    try:
                        selected[rel] = getattr(obj, rel).get(pk=UUID(itm[param]))
                    except:
                        pass

            base = obj.get_price_with_selected(selected)
            now = timezone.now()
            comp = ((getattr(obj,'compare_price',obj.price) or obj.price) +
                    (base - obj.price))
            unit_after = (min(base, comp) if getattr(obj,'discount',False)
                          and getattr(obj,'discount_until',now)>now else base)

            # descuento de ítem
            itm_disc = Decimal('0')
            code = itm.get('coupon_code')
            if code:
                try:
                    cp = Coupon.objects.get(code=code)
                    if cp.is_active():
                        itm_disc = cp.apply_item_discount(base, count)
                except Coupon.DoesNotExist:
                    pass

            total_b = base * count
            total_a = (unit_after * count) - itm_disc
            tax = (total_a * tax_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            preview.append({
                'content_type': itm['content_type'],
                'item_id': itm['item_id'],
                'count': count,
                'unit_before': str(base.quantize(Decimal('0.01'))),
                'unit_after': str(unit_after.quantize(Decimal('0.01'))),
                'total_before': str(total_b.quantize(Decimal('0.01'))),
                'item_discount': str(itm_disc.quantize(Decimal('0.01'))),
                'total_after': str(total_a.quantize(Decimal('0.01'))),
                'tax_amount': str(tax),
            })
            sub_before += total_b
            sub_after  += total_a

        # descuento global
        global_disc = Decimal('0')
        free_ship = False
        if global_code:
            try:
                cp = Coupon.objects.get(code=global_code)
                if cp.is_active():
                    global_disc, free_ship = cp.apply_discount(sub_after, delivery_fee)
                    if not free_ship:
                        sub_after -= global_disc
            except Coupon.DoesNotExist:
                pass

        tax_amount = (sub_after * tax_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total = sub_after + tax_amount + (Decimal('0') if free_ship else delivery_fee)

        return Response({
            'items': preview,
            'subtotal_before': str(sub_before.quantize(Decimal('0.01'))),
            'subtotal_after': str(sub_after.quantize(Decimal('0.01'))),
            'item_discounts': str((sub_before - sub_after).quantize(Decimal('0.01'))),
            'global_discount': str(global_disc.quantize(Decimal('0.01'))),
            'tax_amount': str(tax_amount),
            'delivery_fee': str((Decimal('0') if free_ship else delivery_fee).quantize(Decimal('0.01'))),
            'total': str(total.quantize(Decimal('0.01'))),
        }, status=status.HTTP_200_OK)


class SyncCartView(StandardAPIView):
    """
    POST /cart/sync/

    Body JSON: { "items": [...] }
    Fusiona items de carrito anónimo con el carrito autenticado.
    Devuelve mismo payload que GET /cart/.
    """
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    @transaction.atomic
    def post(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user.id)
        items = request.data.get('items')
        if not isinstance(items, list):
            raise ValidationError('Se requiere lista "items".')

        # Importar aquí los modelos de variante concretos
        from apps.products.models import Size, Weight, Material, Color, Flavor

        for itm in items:
            # 1) Validar content_type/item_id
            ct = get_object_or_404(ContentType, model=itm.get('content_type'))
            oid = itm.get('item_id')
            if not oid:
                raise ValidationError('Falta "item_id" en algún item.')
            count = int(itm.get('count', 1))

            # 2) Construir attrs con variantes explícitas
            attrs = {}
            if 'size_id' in itm:
                try:
                    attrs['size'] = Size.objects.get(pk=UUID(itm['size_id']))
                except Size.DoesNotExist:
                    pass
            if 'weight_id' in itm:
                try:
                    attrs['weight'] = Weight.objects.get(pk=UUID(itm['weight_id']))
                except Weight.DoesNotExist:
                    pass
            if 'material_id' in itm:
                try:
                    attrs['material'] = Material.objects.get(pk=UUID(itm['material_id']))
                except Material.DoesNotExist:
                    pass
            if 'color_id' in itm:
                try:
                    attrs['color'] = Color.objects.get(pk=UUID(itm['color_id']))
                except Color.DoesNotExist:
                    pass
            if 'flavor_id' in itm:
                try:
                    attrs['flavor'] = Flavor.objects.get(pk=UUID(itm['flavor_id']))
                except Flavor.DoesNotExist:
                    pass

            # 3) Añadir al carrito
            add_to_cart_generic(cart, ct, UUID(oid), attrs, count)

        # 4) Devolver el carrito actualizado
        return ListCartView().get(request)


class ShippingOptionsView(StandardAPIView):
    """
    GET /cart/shipping-options/?country=<ISO2>
    """
    permission_classes = [HasValidAPIKey]

    def get(self, request):
        country = request.query_params.get('country', 'PE').upper()
        # Para un CharField que guarda "PE,US,CL", buscamos substring:
        zones = ShippingZone.objects.filter(countries__contains=country)
        methods = ShippingMethod.objects.filter(zone__in=zones, active=True)
        serializer = ShippingMethodSerializer(methods, many=True)
        return Response(serializer.data)
