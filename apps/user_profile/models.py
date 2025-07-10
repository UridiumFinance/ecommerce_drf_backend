import uuid

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.utils.html import format_html
from ckeditor.fields import RichTextField
from djoser.signals import user_registered, user_activated
from apps.assets.models import Media
from apps.assets.serializers import MediaSerializer

User = settings.AUTH_USER_MODEL


class UserProfile(models.Model):

    id = models.UUIDField(default=uuid.uuid4, unique=True, primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    profile_picture = models.ForeignKey(
        Media,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profile_picture",
    )

    banner_picture = models.ForeignKey(
        Media,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="banner_picture",
    )

    biography = RichTextField()
    birthday = models.DateField(blank=True, null=True)

    website = models.URLField(blank=True, default='')
    instagram = models.URLField(blank=True, default='')
    facebook = models.URLField(blank=True, default='')
    threads = models.URLField(blank=True, default='')
    linkedin = models.URLField(blank=True, default='')
    youtube = models.URLField(blank=True, default='')
    tiktok = models.URLField(blank=True, default='')
    github = models.URLField(blank=True, default='')
    gitlab = models.URLField(blank=True, default='')

    def profile_picture_preview(self):
        if self.profile_picture:
            serializer = MediaSerializer(instance=self.profile_picture)
            url = serializer.data.get('url')
            if url:
                return format_html('<img src="{}" style="width: 50px; height: auto;" />', url)
        return 'No Profile Picture'

    def banner_picture_preview(self):
        if self.banner_picture:
            serializer = MediaSerializer(instance=self.banner_picture)
            url = serializer.data.get('url')
            if url:
                return format_html('<img src="{}" style="width: 50px; height: auto;" />', url)
        return 'No Banner Picture'

    profile_picture_preview.short_description = "Profile Picture Preview"
    banner_picture_preview.short_description = "Banner Picture Preview"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Crea un perfil de usuario automáticamente cuando se crea un usuario.
    Reutiliza imágenes predefinidas si ya existen.
    """
    if created:
        profile = UserProfile.objects.create(user=instance)

        # Buscar o crear imagen de perfil
        profile_picture, _ = Media.objects.get_or_create(
            key="media/profiles/default/user_default_profile.png",
            defaults={
                "order": 1,
                "name": "user_default_profile.png",
                "size": "2.3 KB",
                "type": "image/png",  # usar MIME type completo
                "media_type": "image",
            }
        )

        # Buscar o crear imagen de banner
        banner_picture, _ = Media.objects.get_or_create(
            key="media/profiles/default/user_default_banner.jpg",
            defaults={
                "order": 1,
                "name": "user_default_bg.jpg",
                "size": "200.5 KB",
                "type": "image/jpeg",  # usar MIME type completo
                "media_type": "image",
            }
        )

        profile.profile_picture = profile_picture
        profile.banner_picture = banner_picture
        profile.save()