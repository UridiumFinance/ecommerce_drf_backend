from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework_api.views import StandardAPIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import ShippingAddress
from .serializers import ShippingAddressSerializer
from core.permissions import HasValidAPIKey



class ListShippingAddressesView(StandardAPIView):
    """
    GET /shipping/addresses/
    Recupera todas las direcciones de envío del usuario autenticado.
    ---
    Response 200:
        [
            {
                "id": "UUID",
                "user": int,
                "label": str,
                "street": str,
                "city": str,
                "region": str,
                "postal_code": str,
                "country": str,
                "is_default": bool,
                "created_at": datetime,
                "updated_at": datetime
            },
            ...
        ]
    """
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        """
        request:
            - Headers: 
                Authorization: Bearer <jwt_token>
                X-API-KEY: <api_key>
        response:
            - 200 OK: lista de objetos ShippingAddressSerializer
        """
        user = request.user
        addresses = ShippingAddress.objects.filter(user=user)
        serializer = ShippingAddressSerializer(addresses, many=True)
        return self.response(serializer.data)


class DefaultShippingAddressView(StandardAPIView):
    """
    GET /shipping/addresses/default/
    Obtiene la dirección marcada como predeterminada del usuario.
    ---
    Response 200:
        {
            "id": "UUID",
            "user": int,
            "label": str,
            "street": str,
            "city": str,
            "region": str,
            "postal_code": str,
            "country": str,
            "is_default": true,
            "created_at": datetime,
            "updated_at": datetime
        }
    Response 404:
        { "detail": "No default shipping address found." }
    """
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        """
        request:
            - Headers: 
                Authorization: Bearer <jwt_token>
                X-API-KEY: <api_key>
        response:
            - 200 OK: objeto ShippingAddressSerializer de la dirección por defecto
            - 404 Not Found: si no existe ninguna dirección predeterminada
        """
        try:
            default_address = ShippingAddress.objects.get(user=request.user, is_default=True)
        except ShippingAddress.DoesNotExist:
            raise ValidationError("No default shipping address found.")
        serializer = ShippingAddressSerializer(default_address)
        return self.response(serializer.data)


class CreateShippingAddressView(StandardAPIView):
    """
    POST /shipping/addresses/
    Crea una nueva dirección de envío para el usuario autenticado.
    ---
    Request body (application/json):
        {
            "label": "Casa",
            "street": "Calle Falsa 123",
            "city": "Lima",
            "region": "Lima",
            "postal_code": "15001",
            "country": "PE",
            "is_default": false
        }
    Response 201:
        { ...nuevo objeto ShippingAddressSerializer... }
    Response 400:
        { "field": ["error message"], ... }
    """
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        """
        request:
            - Headers:
                Authorization: Bearer <jwt_token>
                X-API-KEY: <api_key>
            - Body JSON: campos para ShippingAddressSerializer (sin id/user/created_at/updated_at)
        response:
            - 201 Created: ShippingAddressSerializer del objeto creado
            - 400 Bad Request: errores de validación
        """
        serializer = ShippingAddressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get('is_default', False):
            # Desmarcar previa predeterminada
            ShippingAddress.objects.filter(
                user=request.user, is_default=True
            ).update(is_default=False)
        serializer.save(user=request.user)
        return self.response(serializer.data, status=status.HTTP_201_CREATED)


class SetDefaultShippingAddressView(StandardAPIView):
    """
    POST /shipping/addresses/{address_id}/default/
    Marca una dirección existente como predeterminada.
    ---
    Path parameters:
        address_id: UUID de la dirección a marcar como default
    Response 200:
        { ...ShippingAddressSerializer actualizado con is_default=true... }
    Response 404:
        { "detail": "Shipping address not found." }
    """
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, address_id):
        """
        request:
            - Headers:
                Authorization: Bearer <jwt_token>
                X-API-KEY: <api_key>
            - No lleva body
        response:
            - 200 OK: ShippingAddressSerializer de la dirección marcada como default
            - 404 Not Found: si la dirección no existe o no pertenece al usuario
        """
        try:
            address = ShippingAddress.objects.get(pk=address_id, user=request.user)
        except ShippingAddress.DoesNotExist:
            raise ValidationError("Shipping address not found.")
        # Desmarcar previa predeterminada
        ShippingAddress.objects.filter(
            user=request.user, is_default=True
        ).update(is_default=False)
        # Marcar esta como predeterminada
        address.is_default = True
        address.save()
        serializer = ShippingAddressSerializer(address)
        return self.response(serializer.data)