from django.urls import path

from .views import (
    ListWishlistView,
    AddWishlistItemView,
    UpdateWishlistItemView,
    RemoveWishlistItemView,
    ClearWishlistView,
    SyncWishlistView,
    MoveCartToWishlistView,
    MoveWishlistToCartView,
)

urlpatterns = [
    path('', ListWishlistView.as_view(), name='list-wishlist-items'),
    path('items/', AddWishlistItemView.as_view(), name='add-wishlist-item'),
    path(
        'items/update/<uuid:wishlist_item_id>/',
        UpdateWishlistItemView.as_view(),
        name='update-wishlist-item'
    ),
    path(
        'items/remove/<uuid:wishlist_item_id>/',
        RemoveWishlistItemView.as_view(),
        name='remove-wishlist-item'
    ),
    path('clear/', ClearWishlistView.as_view(), name='clear-wishlist'),
    path('sync/', SyncWishlistView.as_view(), name='sync-wishlist-items'),
    path(
        'move-from-cart/<uuid:cart_item_id>/',
        MoveCartToWishlistView.as_view(),
        name='move-cart-to-wishlist'
    ),
    path(
        'move-from-wishlist/<uuid:wishlist_item_id>/',
        MoveWishlistToCartView.as_view(),
        name='move-wishlist-to-cart'
    ),
]
