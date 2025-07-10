from django import forms
from django.utils.safestring import mark_safe

from .models import Product, Category
from apps.assets.models import Media
from utils.s3_utils import get_cloudfront_signed_url


class MediaSelectMultipleWidget(forms.CheckboxSelectMultiple):
    def render(self, name, value, attrs=None, renderer=None):
        if value is None:
            value = []
        # Aseguramos que value sea un set de strings
        selected_ids = set(str(v) for v in value)

        output = '<div style="display: flex; flex-wrap: wrap; gap: 16px;">'

        for media in Media.objects.filter(media_type="image"):
            try:
                url = get_cloudfront_signed_url(media.key)
            except Exception:
                url = ""

            checked = 'checked' if str(media.id) in selected_ids else ''
            image_name = media.name or "Sin nombre"

            output += f'''
                <label style="display: flex; flex-direction: column; align-items: center; width: 100px; font-size: 11px; text-align: center;">
                    <input type="checkbox" name="{name}" value="{media.id}" {checked} style="margin-bottom: 4px;" />
                    <div style="
                        width: 80px;
                        height: 80px;
                        border: 1px solid #444;
                        overflow: hidden;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        background: #222;
                        margin-bottom: 4px;
                    ">
                        <img src="{url}" alt="{image_name}" style="max-width: 100%; max-height: 100%; object-fit: cover;" />
                    </div>
                    <div title="{image_name}" style="overflow: hidden; white-space: nowrap; text-overflow: ellipsis; max-width: 100%;">
                        {image_name}
                    </div>
                    <a href="{url}" target="_blank" style="color: #0af; text-decoration: underline; margin-top: 2px;">Ver grande</a>
                </label>
            '''

        output += '</div>'
        return mark_safe(output)


class ProductAdminForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = "__all__"
        widgets = {
            "images": MediaSelectMultipleWidget
        }