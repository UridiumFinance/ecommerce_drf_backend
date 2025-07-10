from uuid import uuid4
from django.db import models
from django.conf import settings
from django_countries.fields import CountryField


class ShippingAddress(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses")
    label      = models.CharField(max_length=50, help_text="p.ej. 'Casa', 'Trabajo'")
    street     = models.CharField(max_length=255)
    city       = models.CharField(max_length=100)
    region     = models.CharField(max_length=100, blank=True)  # provincia, estado…
    postal_code= models.CharField(max_length=20, blank=True)
    country    = CountryField()
    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user","label")]
        ordering = ["-is_default","label"]

    def __str__(self):
        return f"{self.label}: {self.street}, {self.city} ({self.country})"