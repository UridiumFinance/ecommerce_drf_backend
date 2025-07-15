from django.urls import path
from .views import (
    ListShippingAddressesView,
    DefaultShippingAddressView,
    CreateShippingAddressView,
    SetDefaultShippingAddressView
)

urlpatterns = [
    path('', ListShippingAddressesView.as_view(), name='shipping-address-list'),
    path('default/', DefaultShippingAddressView.as_view(), name='shipping-address-default'),
    path('create/', CreateShippingAddressView.as_view(), name='shipping-address-create'),
    path('<uuid:address_id>/default/', SetDefaultShippingAddressView.as_view(), name='shipping-address-set-default'),
]