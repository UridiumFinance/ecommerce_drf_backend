from django.urls import path

from .views import (
    ListCartView, AddCartItemView, UpdateCartItemView,
    RemoveCartItemView, ClearCartView, PreviewCartCalculationView,
    SyncCartView, ShippingOptionsView, CalculateDefaultShippingView
)

urlpatterns = [
    path('', ListCartView.as_view()),
    path('items/', AddCartItemView.as_view()),
    path('items/update/<uuid:cart_item_id>/', UpdateCartItemView.as_view()),
    path('items/remove/<uuid:cart_item_id>/', RemoveCartItemView.as_view()),
    path('clear/', ClearCartView.as_view()),
    path('total/', PreviewCartCalculationView.as_view()),
    path('sync/', SyncCartView.as_view()),
    path('shipping-options/', ShippingOptionsView.as_view()),
    path(
        'shipping/default/',
        CalculateDefaultShippingView.as_view(),
        name='cart-calc-default-shipping'
    ),
]