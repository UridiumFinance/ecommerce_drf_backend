from django.urls import path

from .views import (
    ListProductView,
    DetailProductView,
    UpdateProductAnalyticsView,
    GenerateFakeProductsView,
    ToggleLikeView,
    RegisterShareView,
    CategoryListView,
    UpdateCategoryAnalyticsView,
    AutoCategorizeProducts,
    DetailCategoryView,
    ProductStockView,
    ListProductsByIdView,
    ProductPriceView,
    ListProductsFromCartItemByIdView
)

urlpatterns = [
    path("list/", ListProductView.as_view(), name="product-list"),
    path("detail/", DetailProductView.as_view(), name="product-detail"),
    path("detail/stock/", ProductStockView.as_view(), name="product-stock"),
    path("detail/price/", ProductPriceView.as_view(), name="product-price"),
    path("analytics/update/", UpdateProductAnalyticsView.as_view(), name="product-analytics-update"),
    path("generate-fake/", GenerateFakeProductsView.as_view(), name="generate_fake_products"),
    path("toggle-like/", ToggleLikeView.as_view(), name="toggle-product-like"),
    path("register-share/", RegisterShareView.as_view(), name="register-product-share"),
    path('categories/', CategoryListView.as_view(), name="product-categories-list"),
    path('category/', DetailCategoryView.as_view(), name="product-category"),
    path("analytics/categories/update/", UpdateCategoryAnalyticsView.as_view(), name="category-analytics-update"),
    path("auto-categorize/", AutoCategorizeProducts.as_view()),
    path("list-by-id/", ListProductsByIdView.as_view()),
    path("list-cartitem-by-id/", ListProductsFromCartItemByIdView.as_view()),
]