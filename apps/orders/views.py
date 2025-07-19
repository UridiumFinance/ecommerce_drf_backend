from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Q

from rest_framework import permissions, status, serializers
from rest_framework_api.views import StandardAPIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.db.models import F
from django.conf import settings
from django.shortcuts import get_object_or_404
import stripe

from apps.products.models import ProductInteraction
from utils.ip_utils import get_client_ip, get_device_type
from apps.cart.models import Cart
from .models import Order, OrderItem
from .serializers import OrderSerializer
from core.permissions import HasValidAPIKey

stripe.api_key = settings.STRIPE_SECRET_API_KEY


class ListOrdersView(StandardAPIView):
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        qs = Order.objects.filter(user=request.user)

        # 1) Filtrar por estado si se pasa ?status=
        status_param = request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        # 2) Search en ID o payment_reference con ?search=
        search_param = request.query_params.get("search")
        if search_param:
            qs = qs.filter(
                Q(id__icontains=search_param) |
                Q(payment_reference__icontains=search_param)
            )

        # 3) Ordering con ?ordering=campo o -campo
        ordering = request.query_params.get("ordering")
        if ordering:
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by("-created_at")

        data = OrderSerializer(qs, many=True).data
        return self.paginate(request, data)

    

class DetailOrderView(StandardAPIView):
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        order_id = request.query_params.get("order_id")
        if not order_id:
            return self.error(
                "El parámetro 'order_id' es obligatorio.",
                status=status.HTTP_400_BAD_REQUEST
            )

        order = Order.objects.filter(user=request.user, id=order_id).first()
        if not order:
            return self.response(
                {"error": "Orden no encontrada."},
                status=status.HTTP_404_NOT_FOUND
            )

        data = OrderSerializer(order).data
        return self.response(data)


class ProcessStripePaymentView(StandardAPIView):
    permission_classes = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    class InputSerializer(serializers.Serializer):
        payment_method_id = serializers.CharField(max_length=255)
        shipping_address_id = serializers.UUIDField(required=False)

    def post(self, request):
        # 1) Validar payload
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        payment_method_id = data["payment_method_id"]
        user = request.user

        # 2) Obtener o crear customer en Stripe
        if not user.stripe_customer_id:
            customer = stripe.Customer.create(name=f"{user.first_name} {user.last_name}", email=user.email)
            user.stripe_customer_id = customer.id
            user.save(update_fields=["stripe_customer_id"])
        else:
            customer = stripe.Customer.retrieve(user.stripe_customer_id)

        # 3) Calcular totales del carrito
        cart = get_object_or_404(Cart, user=user.id)
        cart.recalc_shipping()
        subtotal        = cart.subtotal()
        items_discount  = cart.items_discount()
        global_discount, free_shipping = cart.cart_discount()
        shipping_cost   = Decimal("0.00") if free_shipping else cart.shipping_cost
        tax_rate        = Decimal(settings.TAXES)
        taxable         = subtotal - items_discount - global_discount
        tax_amount      = (taxable * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_amount    = (taxable + shipping_cost + tax_amount).quantize(Decimal("0.01"))

        # 4) Crear objeto Order (en estado pending)
        order = Order.objects.create(
            user=user,
            shipping_address=cart.shipping_address,
            shipping_method=cart.shipping_method,
            shipping_cost=shipping_cost,
            coupon=cart.coupon,
            subtotal=subtotal,
            items_discount=items_discount,
            global_discount=global_discount,
            tax_amount=tax_amount,
            total=total_amount,
            status=Order.PENDING,
        )
        # Volcar CartItems a OrderItems
        for ci in cart.items.select_related("content_type","size","weight","material","color","flavor"):
            OrderItem.objects.create(
                order=order,
                content_type=ci.content_type,
                object_id=ci.object_id,
                item_name=str(ci.item),
                unit_price=ci.unit_price(),
                quantity=ci.count,
                item_discount=ci.discount_amount,
                total_price=ci.total_price,
                size_title=getattr(ci.size, "title", ""),
                weight_title=getattr(ci.weight, "title", ""),
                material_title=getattr(ci.material, "title", ""),
                color_title=getattr(ci.color, "title", ""),
                flavor_title=getattr(ci.flavor, "title", ""),
            )

        # 5) Crear y confirmar PaymentIntent en Stripe
        try:
            # a) Adjuntamos el método de pago al cliente
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer.id,
            )
            # b) Lo marcamos como predeterminado
            stripe.Customer.modify(
                customer.id,
                invoice_settings={"default_payment_method": payment_method_id}
            )
            # c) Creamos el PaymentIntent
            intent = stripe.PaymentIntent.create(
                amount=int(total_amount * 100),          # convierte a centavos
                currency=getattr(settings, "CURRENCY", "usd"),
                customer=customer.id,
                payment_method=payment_method_id,
                off_session=True,
                confirm=True,
                metadata={"order_id": str(order.id)},
            )
        except stripe.error.CardError as e:
            # Pago rechazado por la tarjeta
            order.status = Order.FAILED
            order.save(update_fields=["status"])
            return self.response(
                {"error": e.user_message},
                success=False,
                status=status.HTTP_402_PAYMENT_REQUIRED
            )
        except stripe.error.StripeError as e:
            # Cualquier otro error de Stripe
            order.status = Order.FAILED
            order.save(update_fields=["status"])
            return self.response(
                {"error": str(e)},
                success=False,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 6) Si llegamos aquí, el pago fue exitoso
        order.payment_reference = intent.get("id")
        order.status            = Order.PAID
        order.save(update_fields=["payment_reference", "status"])

        # --- 7) Ajustar stock de productos y variantes ---
        for ci in cart.items.select_related(
            "content_type", "size", "weight", "material", "color", "flavor"
        ):
            # Sólo nos importa Product
            if ci.content_type.model == "product":
                # Reducir stock en cada variante
                for attr in ("size", "weight", "material", "color", "flavor"):
                    variant = getattr(ci, attr)
                    if variant and hasattr(variant, "stock"):
                        variant.stock = F("stock") - ci.count
                        variant.save(update_fields=["stock"])

                # (Opcional) Reducir stock global del producto
                prod = ci.item  # instancia de Product
                if hasattr(prod, "stock"):
                    prod.stock = F("stock") - ci.count
                    prod.save(update_fields=["stock"])

        # --- 8) Registrar uso de cupón ---
        if cart.coupon:
            # actualiza uses_count y crea CouponRedemption
            cart.coupon.record_usage(user, order)

        # --- 9) Crear interacciones de compra para analíticas ---
        session_id  = request.session.session_key or ""
        ip_address  = get_client_ip(request)
        device_type = get_device_type(request)

        for ci in cart.items.select_related("content_type"):
            if ci.content_type.model == "product":
                variant_metadata = {}
                for attr in ("size", "weight", "material", "color", "flavor"):
                    variant = getattr(ci, attr)
                    if variant:
                        variant_metadata[attr] = {
                            "id": str(variant.id),
                            "title": variant.title,
                            # opcionalmente añades precio o stock
                            "price": str(variant.price),
                            "stock": variant.stock,
                        }

                # Y luego en la creación de la interacción:
                ProductInteraction.objects.create(
                    user=request.user,
                    product=ci.item,
                    session_id=session_id,
                    interaction_type="purchase",
                    quantity=ci.count,
                    total_price=ci.total_price,
                    order_id=str(order.id),
                    ip_address=ip_address,
                    device_type=device_type,
                    metadata=variant_metadata
                )

        # --- 10) Limpiar carrito y responder ---
        cart.items.all().delete()
        return self.response({
            "order_id":         order.id,
            "payment_intent_id": intent.id,
            "payment_status":    intent.status,
        }, status=status.HTTP_200_OK)