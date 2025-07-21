from django.urls import path
from .views import SubmitComplaintView

urlpatterns = [
    path('send/', SubmitComplaintView.as_view(), name='submit_complaint'),
]
