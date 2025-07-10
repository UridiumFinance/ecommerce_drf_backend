from uuid import UUID

from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework_api.views import StandardAPIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.contrib.contenttypes.models import ContentType

from .models import Wishlist, WishlistItem
from .serializers import WishlistSerializer, WishlistItemSerializer
from core.permissions import HasValidAPIKey
from apps.cart.models import Cart, CartItem
from apps.cart.views import ListCartView


class ListWishlistView(StandardAPIView):
    """
    GET /wishlist/

    Devuelve la wishlist del usuario (la crea si no existe).
    Respuesta 200:
    {
      "id": <uuid>,
      "items": [ ... ]
    }
    """
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        wishlist, _ = Wishlist.objects.prefetch_related(
            'items__item',
            'items__size', 'items__weight',
            'items__material', 'items__color', 'items__flavor'
        ).get_or_create(user=request.user.id)
        serializer = WishlistSerializer(wishlist, context={'request': request})
        return self.response(serializer.data)


class AddWishlistItemView(StandardAPIView):
    """
    POST /wishlist/items/

    Body JSON:
      {
        "content_type": "product|course|... ",
        "object_id": "<uuid>",
        "size_id": <int>, "weight_id": <int>, ...  # opcional
      }

    Respuesta 201: mismo payload que GET /wishlist/.
    """
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    @transaction.atomic
    def post(self, request):
        wishlist, _ = Wishlist.objects.get_or_create(user=request.user.id)
        serializer = WishlistItemSerializer(
            data=request.data,
            context={'wishlist': wishlist, 'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return ListWishlistView().get(request)


class UpdateWishlistItemView(StandardAPIView):
    """
    PATCH /wishlist/items/<wishlist_item_id>/

    Body JSON (parcial):
      { "size_id": <int>, "color_id": <int>, ... }

    Actualiza variantes de un WishlistItem. Devuelve GET /wishlist/.
    """
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    @transaction.atomic
    def patch(self, request, wishlist_item_id=None):
        if not wishlist_item_id:
            raise ValidationError("Falta <wishlist_item_id> en la URL.")
        wishlist = get_object_or_404(Wishlist, user=request.user.id)
        wi = get_object_or_404(WishlistItem, id=wishlist_item_id, wishlist=wishlist)
        serializer = WishlistItemSerializer(
            wi,
            data=request.data,
            partial=True,
            context={'wishlist': wishlist, 'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return ListWishlistView().get(request)


class RemoveWishlistItemView(StandardAPIView):
    """
    DELETE /wishlist/items/<wishlist_item_id>/

    Elimina un ítem de la wishlist. Devuelve GET /wishlist/.
    """
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    http_method_names      = ['delete']

    @transaction.atomic
    def delete(self, request, wishlist_item_id=None):
        if not wishlist_item_id:
            raise ValidationError("Falta <wishlist_item_id> en la URL.")
        wishlist = get_object_or_404(Wishlist, user=request.user.id)
        wi = get_object_or_404(WishlistItem, id=wishlist_item_id, wishlist=wishlist)
        wi.delete()
        return ListWishlistView().get(request)


class ClearWishlistView(StandardAPIView):
    """
    POST /wishlist/clear/

    Elimina todos los ítems de la wishlist.
    Respuesta 200: { "message": "Wishlist limpiada." }
    """
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        wishlist = get_object_or_404(Wishlist, user=request.user.id)
        wishlist.items.all().delete()
        return Response({'message': 'Wishlist limpiada.'}, status=status.HTTP_200_OK)


class SyncWishlistView(StandardAPIView):
    """
    POST /wishlist/sync/

    Body JSON: { "items": [ { "content_type": ..., "object_id": ..., ... }, ... ] }
    Fusiona una lista de ítems (por ejemplo, desde localStorage) con la wishlist autenticada.
    Responde con el payload de GET /wishlist/.
    """
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    @transaction.atomic
    def post(self, request):
        wishlist, _ = Wishlist.objects.get_or_create(user=request.user.id)
        items = request.data.get('items')
        if not isinstance(items, list):
            raise ValidationError('Se requiere lista "items".')

        for itm in items:
            ct = get_object_or_404(ContentType, model=itm.get('content_type'))
            oid = itm.get('item_id')
            if not oid:
                raise ValidationError('Falta "item_id" en algún ítem.')
            # variantes opcionales
            attrs = {}
            for rel, field in (
                ('size', 'size_id'),
                ('weight', 'weight_id'),
                ('material', 'material_id'),
                ('color', 'color_id'),
                ('flavor', 'flavor_id'),
            ):
                if itm.get(field):
                    try:
                        attrs[rel] = getattr(wishlist, rel + 's').model.objects.get(pk=UUID(itm[field]))
                    except Exception:
                        pass
            # crea o actualiza
            WishlistItem.objects.get_or_create(
                wishlist=wishlist,
                content_type=ct,
                object_id=oid,
                defaults=attrs
            )

        return ListWishlistView().get(request)


class MoveCartToWishlistView(StandardAPIView):
    """
    POST /wishlist/move-from-cart/<cart_item_id>/

    Mueve un ítem del carrito a la wishlist y lo elimina del carrito.
    Responde con el payload de GET /wishlist/.
    """
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    http_method_names      = ['post']

    @transaction.atomic
    def post(self, request, cart_item_id=None):
        if not cart_item_id:
            raise ValidationError("Falta <cart_item_id> en la URL.")
        # 1) Obtener carrito y cart item
        cart = get_object_or_404(Cart, user=request.user.id)
        ci   = get_object_or_404(CartItem, id=cart_item_id, cart=cart)

        # 2) Obtener o crear wishlist
        wishlist, _ = Wishlist.objects.get_or_create(user=request.user.id)

        # 3) Crear o actualizar WishlistItem
        WishlistItem.objects.get_or_create(
            wishlist=wishlist,
            content_type=ci.content_type,
            object_id=ci.object_id,
            defaults={
                'size':     ci.size,
                'weight':   ci.weight,
                'material': ci.material,
                'color':    ci.color,
                'flavor':   ci.flavor,
            }
        )

        # 4) Eliminar del carrito
        ci.delete()

        # 5) Devolver wishlist actualizada
        return ListWishlistView().get(request)


class MoveWishlistToCartView(StandardAPIView):
    """
    POST /cart/move-from-wishlist/<wishlist_item_id>/

    Mueve un ítem de la wishlist al carrito y lo elimina de la wishlist.
    Responde con el payload de GET /cart/.
    """
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    http_method_names      = ['post']

    @transaction.atomic
    def post(self, request, wishlist_item_id=None):
        if not wishlist_item_id:
            raise ValidationError("Falta <wishlist_item_id> en la URL.")
        # 1) Obtener wishlist y wishlist item
        wishlist = get_object_or_404(Wishlist, user=request.user.id)
        wi       = get_object_or_404(WishlistItem, id=wishlist_item_id, wishlist=wishlist)

        # 2) Obtener o crear carrito
        cart, _ = Cart.objects.get_or_create(user=request.user.id)

        # 3) Añadir al carrito
        attrs = {
            'size':     wi.size,
            'weight':   wi.weight,
            'material': wi.material,
            'color':    wi.color,
            'flavor':   wi.flavor,
        }
        from apps.cart.utils import add_to_cart_generic
        add_to_cart_generic(cart, wi.content_type, wi.object_id, attrs, quantity=1)

        # 4) Eliminar de la wishlist
        wi.delete()

        # 5) Devolver carrito actualizado
        return ListCartView().get(request)