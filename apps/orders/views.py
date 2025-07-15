from decimal import Decimal, ROUND_HALF_UP

from rest_framework import permissions, status, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework_api.views import StandardAPIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings
from django.shortcuts import get_object_or_404
import stripe

from apps.cart.models import Cart
from .models import Order, OrderItem
from core.permissions import HasValidAPIKey

stripe.api_key = settings.STRIPE_SECRET_API_KEY


class ProcessStripePaymentView(StandardAPIView):
    permission_classes = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    class InputSerializer(serializers.Serializer):
        method = serializers.ChoiceField(choices=["creditCard", "paypal", "mercadoPago"])
        data   = serializers.DictField()

    def post(self, request):
        # 1) Validar payload
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        method = serializer.validated_data["method"]
        data   = serializer.validated_data["data"]
        user = request.user

        if method != "creditCard":
            return self.response("Sólo tarjeta implementado", status=status.HTTP_400_BAD_REQUEST)
        
        # 2) Extraer datos de la tarjeta
        try:
            name       = data["nameOnCard"]
            number     = data["cardNumber"].replace(" ", "")
            exp_month  = int(data["expiryMonth"])
            exp_year   = 2000 + int(data["expiryYear"])
            cvc        = data["cvc"]
        except KeyError as e:
            return self.response(f"Falta el campo {e.args[0]}", status=status.HTTP_400_BAD_REQUEST)

        print(f"""
        Credit card details:
            name: {name}
            number: {number}
            exp_month: {exp_month}
            exp_year: {exp_year}
            cvc: {cvc}
        """)

        # 3) Obtener o crear customer en Stripe
        if not user.stripe_customer_id:
            customer = stripe.Customer.create(name=f"{user.first_name} {user.last_name}", email=user.email)
            user.stripe_customer_id = customer.id
            user.save(update_fields=["stripe_customer_id"])
        else:
            customer = stripe.Customer.retrieve(user.stripe_customer_id)

        # 4) Calcular totales del carrito
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

        print(f"""
        Cart totals:
            subtotal: {subtotal}
            items_discount: {items_discount}
            global_discount: {global_discount}
            shipping_cost: {shipping_cost}
            tax_rate: {tax_rate}
            taxable: {taxable}
            tax_amount: {tax_amount}
            total_amount: {total_amount}
        """)

        # 5) Crear objeto Order (en estado pending)
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

        # 6) Crear PaymentMethod en Stripe
        

        return self.response("TEST")