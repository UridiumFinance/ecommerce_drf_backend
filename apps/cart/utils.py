from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from .models import Cart, CartItem

@transaction.atomic
def add_to_cart_generic(cart, content_type, object_id, attrs, quantity):
    ct = ContentType.objects.get_for_model(content_type.model_class())
    ci, created = CartItem.objects.select_for_update().get_or_create(
        cart=cart,
        content_type=ct,
        object_id=object_id,
        size=attrs.get('size'),
        weight=attrs.get('weight'),
        material=attrs.get('material'),
        color=attrs.get('color'),
        flavor=attrs.get('flavor'),
        defaults={'count': 0}
    )
    ci.count = F('count') + quantity
    ci.save(update_fields=['count'])
    return ci

# Merge carrito anónimo con autenticado
def merge_carts(anon_cart, user_cart):
    """
    Fusiona items de anon_cart en user_cart, sumando counts y respetando atributos.
    """
    for item in anon_cart.items.all():
        add_to_cart_generic(
            user_cart,
            ContentType.objects.get_for_model(item.item),
            item.object_id,
            {
                'size': item.size,
                'weight': item.weight,
                'material': item.material,
                'color': item.color,
                'flavor': item.flavor,
            },
            item.count
        )
    anon_cart.items.all().delete()
    anon_cart.delete()

def purge_old_carts(self, *args, **options):
        '''
        'Elimina carritos inactivos desde hace más de 30 días'
        '''
        cutoff = timezone.now() - timedelta(days=30)
        old = Cart.objects.filter(created_at__lt=cutoff)
        count = old.count()
        old.delete()
        self.stdout.write(f"Se eliminaron {count} carritos inactivos.")


def get_recommendations_for_cart(cart, num=5):
    """
    Recomendaciones genéricas a partir de los ítems en el carrito.
    Por ahora sólo maneja productos: sugiere hasta `num` productos
    de la misma categoría que los que ya están en el carrito.
    """
    from django.contrib.contenttypes.models import ContentType
    from apps.products.models import Product

    # 1) Recolectar todos los CartItem
    items = cart.items.all().select_related('content_type')

    # 2) Filtrar sólo los de modelo "product"
    product_ct = ContentType.objects.get_for_model(Product)
    prod_items = [ci for ci in items if ci.content_type_id == product_ct.id]

    # 3) Sacar IDs de categoría de los productos en carrito
    cat_ids = {
        ci.item.category_id
        for ci in prod_items
        if getattr(ci.item, 'category_id', None) is not None
    }

    # 4) Base queryset de Product
    qs = Product.postobjects.all()

    # 5) Si tenemos categorías, filtrar por ellas
    if cat_ids:
        qs = qs.filter(category_id__in=cat_ids)

    # 6) Excluir los productos ya en el carrito
    in_cart_ids = [ci.object_id for ci in prod_items]
    if in_cart_ids:
        qs = qs.exclude(id__in=in_cart_ids)

    # 7) Devolver hasta `num` ítems (aleatorio para variabilidad)
    return qs.order_by('?')[:num]