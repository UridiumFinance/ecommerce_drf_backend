from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from .models import Review
from apps.products.models import ProductInteraction, ProductAnalytics
from utils.ip_utils import get_client_ip
from apps.authentication.serializers import UserPublicSerializer

class ReviewSerializer(serializers.ModelSerializer):
    # Representamos el ContentType por su slug (model name)
    content_type = serializers.SlugRelatedField(
        slug_field='model',
        queryset=ContentType.objects.all(),
        help_text="Modelo al que pertenece la reseña (e.g. 'product')"
    )
    # Ahora como UUIDField en lugar de IntegerField
    object_id = serializers.UUIDField(
        help_text="UUID del objeto reseñado"
    )
    content_object = serializers.SerializerMethodField(read_only=True)
    user = UserPublicSerializer(read_only=True)

    class Meta:
        model = Review
        fields = [
            'id',
            'content_type',
            'object_id',
            'content_object',
            'user',
            'rating',
            'title',
            'body',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ('id', 'content_object', 'user', 'created_at', 'updated_at')

    def get_content_object(self, obj):
        return str(obj.content_object)

    def create(self, validated_data):
        request = self.context['request']
        # 1) Asignamos el usuario actual al validated_data
        validated_data['user'] = request.user

        # 2) Guardamos la reseña con user ya presente
        review = super().create(validated_data)

        # 3) Si es un producto, creamos la interacción "rate"
        ct = validated_data['content_type']
        if ct.model == 'product':
            ProductInteraction.objects.create(
                user             = request.user,
                product          = review.content_object,
                interaction_type = 'rate',
                rating           = review.rating,
                review           = review.body,
                ip_address       = get_client_ip(request)
            )

        return review
    
    def update(self, instance, validated_data):
        # 1) Guardamos la reseña y conservamos el rating antiguo
        old_rating = instance.rating
        review = super().update(instance, validated_data)

        # 2) Si es una reseña de producto, sincronizamos interacción + analytics
        if instance.content_type.model == 'product':
            user = self.context['request'].user
            product = review.content_object

            # -- Interacción "rate": actualizar o crear si faltara --
            interaction, created = ProductInteraction.objects.get_or_create(
                user=user,
                product=product,
                interaction_type='rate',
                defaults={
                    'rating': review.rating,
                    'review': review.body
                }
            )
            if not created:
                interaction.rating = review.rating
                interaction.review = review.body
                interaction.save(update_fields=['rating', 'review'])

            # -- Recalcular métricas en ProductAnalytics desde cero --
            analytics, _ = ProductAnalytics.objects.get_or_create(product=product)
            qs = ProductInteraction.objects.filter(
                product=product,
                interaction_type='rate'
            )
            ratings = list(qs.values_list('rating', flat=True))
            if ratings:
                analytics.review_count = len(ratings)
                analytics.average_rating = sum(ratings) / len(ratings)
            else:
                analytics.review_count = 0
                analytics.average_rating = 0.0
            analytics.save(update_fields=['review_count', 'average_rating'])

        return review
