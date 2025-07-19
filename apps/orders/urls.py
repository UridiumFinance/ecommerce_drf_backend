from django.urls import path

from .views import ProcessStripePaymentView, ListOrdersView, DetailOrderView

urlpatterns = [
    path('list/', ListOrdersView.as_view()),
    path('detail/', DetailOrderView.as_view()),
    path('process_stripe_payment/', ProcessStripePaymentView.as_view()),
]