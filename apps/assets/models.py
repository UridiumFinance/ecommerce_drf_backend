import uuid

from django.db import models
from django.utils.html import format_html
from django.contrib import admin

from utils.s3_utils import get_cloudfront_signed_url


class Media(models.Model):
    MEDIA_TYPES = (
        ("image", "Image"),
        ("video", "Video"),
        ("document", "Document"),
        ("audio", "Audio"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.PositiveIntegerField(default=0)
    name = models.CharField(max_length=256)
    size = models.CharField(max_length=256)
    type = models.CharField(max_length=256)
    key = models.CharField(max_length=256)
    media_type = models.CharField(max_length=30, choices=MEDIA_TYPES)

    def __str__(self):
        return self.name or str(self.id)

    @admin.display(description="Preview")
    def image_preview(self):
        if self.media_type == "image" and self.key:
            try:
                url = get_cloudfront_signed_url(self.key)
                if url:
                    return format_html('<img src="{}" style="width: 60px; height: auto;" />', url)
            except Exception as e:
                return f"Error: {str(e)}"
        return "—"

    @admin.display(description="Vista previa")
    def image_display(self):
        if self.media_type == "image" and self.key:
            try:
                url = get_cloudfront_signed_url(self.key)
                return format_html('<img src="{}" style="max-width: 300px; height: auto; border:1px solid #ccc;" />', url)
            except Exception as e:
                return f"Error: {str(e)}"
        return "—"