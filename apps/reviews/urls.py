from django.urls import path
from .views import ListReviewsView, ReviewView

app_name = 'reviews'

urlpatterns = [
    # Listar reseñas de un objeto: GET /reviews/?content_type=product&object_id=1
    path('', ListReviewsView.as_view(), name='review-list'),
    # Operaciones sobre reseña individual: GET/POST/PUT /reviews/detail/?id=1
    path('detail/', ReviewView.as_view(), name='review-detail'),
]