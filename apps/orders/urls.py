from django.urls import path

from .views import ProcessStripePaymentView

urlpatterns = [
    path('process_stripe_payment/', ProcessStripePaymentView.as_view()),
]