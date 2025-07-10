from django.db.models.signals import post_save
from django.contrib.auth.signals import user_logged_in

from django.dispatch import receiver
from .models import Cart, CartItem
from apps.authentication.models import UserAccount
from apps.products.models import ProductInteraction, ProductAnalytics
from .utils import merge_carts

@receiver(post_save, sender=UserAccount)
def create_cart(sender, instance, created, **kwargs):
    if created:
        Cart.objects.create(user=instance.id)

@receiver(user_logged_in)
def merge_anonymous_cart(sender, user, request, **kwargs):
    anon_id = request.session.get('cart_id')
    if not anon_id:
        return
    try:
        anon_cart = Cart.objects.get(id=anon_id)
        user_cart = Cart.objects.get(user=user.id)
        merge_carts(anon_cart, user_cart)
    except Cart.DoesNotExist:
        pass

# @receiver(post_save, sender=CartItem)
# def record_cartitem_metrics(sender, instance, created, **kwargs):
#     # sólo un ejemplo — ajusta interaction_type, categorías, etc. según tu lógica
#     ProductInteraction.objects.create(
#         product=instance.item,
#         user=instance.cart.user,             # o como obtengas el usuario
#         interaction_type='add_to_cart',
#         interaction_category='cart',         # si lo usas
#         quantity=instance.count,             # ← aquí usas quantity, no count
#         total_price=instance.total_price,    # si tu campo se llama total_price
#         order_id=None,                       # u otro valor si procede
#         ip_address=instance.cart.session_id, # o como obtengas la IP
#         device_type=None,                    # si lo usas
#         hour_of_day=instance.added_at.hour,  # o timezone.now().hour
#         day_of_week=instance.added_at.weekday(),
#         metadata={},                         # o lo que guardes
#     )
