from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('api/authentication/', include("apps.authentication.urls")),
    path('api/profile/', include("apps.user_profile.urls")),
    path('api/products/', include("apps.products.urls")),
    path('api/cart/', include("apps.cart.urls")),
    path('api/wishlist/', include("apps.wishlist.urls")),
    path('api/addresses/', include("apps.addresses.urls")),
    path('api/orders/', include("apps.orders.urls")),


    path("auth/", include("djoser.urls")),
    path("auth/", include("djoser.urls.jwt")),
    path('sudo/', admin.site.urls),
]

# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
