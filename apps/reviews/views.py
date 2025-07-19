from django.db.models import Avg, Count
from rest_framework import permissions, status
from rest_framework_api.views import StandardAPIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from django.contrib.contenttypes.models import ContentType

from core.permissions import HasValidAPIKey
from .models import Review
from .serializers import ReviewSerializer


class ListReviewsView(StandardAPIView):
    """
    GET /reviews/?content_type=<model>&object_id=<id>
      → Lista todas las reseñas activas para ese objeto.
    """
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        content_model = request.query_params.get('content_type')
        object_id     = request.query_params.get('object_id')
        if not content_model or not object_id:
            return self.response(
                {'detail': 'Los parámetros content_type y object_id son obligatorios.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            ct = ContentType.objects.get(model=content_model)
        except ContentType.DoesNotExist:
            return self.response(
                {'detail': f'content_type inválido: {content_model}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        qs = Review.objects.filter(
            content_type=ct,
            object_id=object_id,
            is_active=True
        ).order_by('-created_at')

        # 1) Estadísticas generales
        stats = qs.aggregate(
            average=Avg('rating'),
            totalCount=Count('id')
        )
        avg = stats['average'] or 0.0
        total = stats['totalCount'] or 0

        # 2) Conteo por rating (5→1)
        raw_counts = qs.values('rating').annotate(count=Count('rating'))
        counts = [
            {
                'rating': r,
                'count': next((c['count'] for c in raw_counts if c['rating'] == r), 0)
            }
            for r in range(5, 0, -1)
        ]

        serialized = ReviewSerializer(qs, many=True)
        additional_data = {
            "average": round(avg, 1),
            "totalCount": total,
            "counts": counts,
        }
        return self.paginate_with_extra(request, serialized.data, extra_data=additional_data)
    

class ReviewView(StandardAPIView):
    """
    GET    /reviews/?id=<pk>   → Recupera una reseña por su PK.
    POST   /reviews/          → Crea una nueva reseña.
    PUT    /reviews/          → Actualiza una reseña existente.
    """
    permission_classes     = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        """
        Recupera la reseña del usuario autenticado para un objeto específico.

        Endpoint:
            GET /reviews/detail/?content_type=<modelo>&object_id=<id>

        Query Params:
            content_type (str): Slug del modelo (e.g. "product", "course").
            object_id (int): ID del objeto reseñado.

        Respuestas:
            200 OK: Retorna los datos de la reseña.
            400 BAD REQUEST: Si falta content_type u object_id.
            404 NOT FOUND: Si no existe ninguna reseña para ese usuario y objeto.
        """
        model = request.query_params.get('content_type')
        object_id = request.query_params.get('object_id')
        if not model or not object_id:
            return self.response(
                {'detail': 'Los parámetros content_type y object_id son obligatorios.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        ct = get_object_or_404(ContentType, model=model)
        review = get_object_or_404(
            Review,
            content_type=ct,
            object_id=object_id,
            user=request.user
        )
        serialized = ReviewSerializer(review, context={'request': request})
        return self.response(serialized.data)

    def post(self, request):
        """
        Crea una nueva reseña para un objeto reseñable.
        Si el usuario ya tiene una reseña para ese mismo objeto,
        devuelve 400 BAD REQUEST.
        """
        content_type_slug = request.data.get('content_type')
        object_id         = request.data.get('object_id')

        if not content_type_slug or not object_id:
            return self.response(
                {'detail': 'Los campos content_type y object_id son obligatorios.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Obtenemos el ContentType
        ct = get_object_or_404(ContentType, model=content_type_slug)

        # Si ya existe una reseña de este user para este objeto, abortamos
        if Review.objects.filter(
            content_type=ct,
            object_id=object_id,
            user=request.user
        ).exists():
            return self.response(
                {'detail': 'Ya has agregado una reseña para este objeto.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Si no existe, procedemos a crear
        serializer = ReviewSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request):
        """
        Actualiza una reseña existente si el usuario es el autor.

        Endpoint:
            PUT /reviews/detail/

        Body (JSON):
            {
                "id": <int>,                # ID de la reseña a actualizar
                "content_type": "product",  # (Opcional) Slug del modelo
                "object_id": 123,           # (Opcional) ID del objeto
                "rating": 1-5,              # (Opcional) Nueva calificación
                "title": "Nuevo título",    # (Opcional) Nuevo título
                "body": "Nuevo texto",      # (Opcional) Nuevo contenido
                "is_active": true|false     # (Opcional) Visibilidad
            }

        Respuestas:
            200 OK: Reseña actualizada con éxito.
            400 BAD REQUEST: Si falta el campo id.
            403 FORBIDDEN: Si el usuario no es el autor de la reseña.
            404 NOT FOUND: Si la reseña no existe.
        """
        review_id = request.data.get('id')
        if not review_id:
            return self.response(
                {'detail': 'El campo id es obligatorio para actualizar.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        review = get_object_or_404(Review, pk=review_id)
        if review.user != request.user:
            return self.response(
                {'detail': 'No tienes permiso para modificar esta reseña.'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = ReviewSerializer(review, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.response(serializer.data)