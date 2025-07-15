from rest_framework import serializers
from .models import ShippingAddress

from utils.string_utils import sanitize_string

class ShippingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = '__all__'
        read_only_fields = ('id','user','created_at','updated_at')

    def validate_label(self, value):
        # Solo letras, números, espacios, comas, puntos…
        return sanitize_string(value)

    def validate_street(self, value):
        return sanitize_string(value)

    def validate_city(self, value):
        return sanitize_string(value)

    def validate_region(self, value):
        return sanitize_string(value)

    def validate_postal_code(self, value):
        # Puede ser alfanumérico, guiones…
        return sanitize_string(value)

    def validate_country(self, value):
        # CountryField de django-countries ya valida el código ISO, no hace falta sanear
        return value