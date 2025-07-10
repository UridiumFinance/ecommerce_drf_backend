from django.contrib import admin
from django.utils.text import slugify
from django.utils.html import format_html
from django.db import models
from django.forms import NumberInput

from .models import (
    Product, ProductInteraction, ProductAnalytics,
    Detail, Requisite, Benefit, WhoIsFor,
    Color, Size, Material, Weight, Flavor,
    Category, CategoryInteraction, CategoryAnalytics
)
from .forms import ProductAdminForm
    

# --- Inlines (edición embebida) ---

class DetailInline(admin.TabularInline):
    model = Detail
    extra = 1
    ordering = ['order']
    fields = ('show_id', 'order', 'title', 'description')
    readonly_fields = ('show_id',)

    def show_id(self, obj):
        return obj.pk
    show_id.short_description = "ID"


class RequisiteInline(admin.TabularInline):
    model = Requisite
    extra = 1
    ordering = ['order']
    fields = ('show_id', 'order', 'title')
    readonly_fields = ('show_id',)

    def show_id(self, obj):
        return obj.pk
    show_id.short_description = "ID"


class BenefitInline(admin.TabularInline):
    model = Benefit
    extra = 1
    ordering = ['order']
    fields = ('show_id', 'order', 'title')
    readonly_fields = ('show_id',)

    def show_id(self, obj):
        return obj.pk
    show_id.short_description = "ID"


class WhoIsForInline(admin.TabularInline):
    model = WhoIsFor
    extra = 1
    ordering = ['order']
    fields = ('show_id', 'order', 'title')
    readonly_fields = ('show_id',)

    def show_id(self, obj):
        return obj.pk
    show_id.short_description = "ID"


class ColorInline(admin.TabularInline):
    model = Color
    extra = 1
    ordering = ['order']
    fields = ('show_id', 'order', 'title', 'hex', 'price', 'stock')
    readonly_fields = ('show_id',)

    def show_id(self, obj):
        return obj.pk
    show_id.short_description = "ID"


class SizeInline(admin.TabularInline):
    model = Size
    extra = 1
    ordering = ['order']
    fields = ('show_id', 'order', 'title', 'price', 'stock')
    readonly_fields = ('show_id',)

    def show_id(self, obj):
        return obj.pk
    show_id.short_description = "ID"


class MaterialInline(admin.TabularInline):
    model = Material
    extra = 1
    ordering = ['order']
    fields = ('show_id', 'order', 'title', 'price', 'stock')
    readonly_fields = ('show_id',)

    def show_id(self, obj):
        return obj.pk
    show_id.short_description = "ID"


class WeightInline(admin.TabularInline):
    model = Weight
    extra = 1
    ordering = ['order']
    fields = ('show_id', 'order', 'title', 'price', 'stock')
    readonly_fields = ('show_id',)

    def show_id(self, obj):
        return obj.pk
    show_id.short_description = "ID"


class FlavorInline(admin.TabularInline):
    model = Flavor
    extra = 1
    ordering = ['order']
    fields = ('show_id', 'order', 'title', 'price', 'stock')
    readonly_fields = ('show_id',)

    def show_id(self, obj):
        return obj.pk
    show_id.short_description = "ID"


class ChildCategoryInline(admin.TabularInline):
    model = Category
    fk_name = "parent"
    extra = 0               # no mostrar renglones vacíos extra
    fields = ("name", "slug", "thumbnail",)  # los campos que quieras editar inline
    readonly_fields = ("thumbnail_preview",)

# --- Admin principal del modelo Category ---
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    inlines = [ChildCategoryInline]

    list_display = (
        "name",
        "thumbnail_preview",
        "parent",
        "children_list",
        "slug"
    )

    list_editable = ("slug",)

    list_filter = ("name", "parent", "slug")
    search_fields = ("id", "title", "name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("thumbnail_preview",)
    fieldsets = (
        (None, {
            'fields': (
                'name',
                'title',
                'description',
                'parent',
            ),
            'description': 'Información básica de la categoría'
        }),
        ('Media y URL', {
            'fields': (
                'thumbnail',
                'thumbnail_preview',
                'slug',
            ),
            'description': 'Miniatura y slug de la categoría'
        }),
    )

    ordering = ("parent__name", "name")

    def save_model(self, request, obj, form, change):
        if not obj.slug:
            obj.slug = slugify(obj.title)
        super().save_model(request, obj, form, change)

    def children_list(self, obj):
        return ", ".join(child.name for child in obj.children.all()) or "—"
    children_list.short_description = "Children"


@admin.register(CategoryInteraction)
class CategoryInteractionAdmin(admin.ModelAdmin):
    list_display = ("category", "user", "interaction_type", "timestamp", "ip_address")
    list_filter = (
        'interaction_type', 'device_type', 'category', 'user',
    )
    search_fields = (
        'session_id', 'metadata', 'user__username', 'category__name',
    )
    date_hierarchy = 'timestamp'
    readonly_fields = ('timestamp',)


@admin.register(CategoryAnalytics)
class CategoryAnalyticsAdmin(admin.ModelAdmin):
    list_display = ("category", "views", "purchases", "conversion_rate", "revenue_generated")
    readonly_fields = [field.name for field in CategoryAnalytics._meta.fields if field.name != "id"]

    list_filter = (
        'category',
    )
    search_fields = (
        'category__name',
    )

    fieldsets = (
        ('Tráfico general', {
            'fields': (
                'impressions', 'clicks', 'click_through_rate',
                'views', 'first_viewed_at', 'last_viewed_at', 'avg_time_on_page',
            )
        }),
        ('Interacciones sociales', {
            'fields': (
                'likes', 'shares', 'wishlist_count',
            )
        }),
        ('Conversiones y comercio', {
            'fields': (
                'add_to_cart_count', 'purchases', 'conversion_rate',
                'revenue_generated', 'avg_order_value',
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at',),
        }),
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm

    list_display = (
        "title",
        "thumbnail_preview",
        "price",
        "compare_price",
        "stock",
        "status_badge",
        "created_at",
    )
    list_editable = ("price", "compare_price", "stock",)

    formfield_overrides = {
        models.DecimalField: {'widget': NumberInput(attrs={'step': '1'})},
        models.IntegerField: {'widget': NumberInput(attrs={'step': '1'})},
    }
    list_filter = ("status", "condition", "packaging", "created_at")
    search_fields = ("title", "description", "keywords", "slug")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "thumbnail_preview", "id")

    autocomplete_fields = ['thumbnail']

    inlines = [
        DetailInline,
        RequisiteInline,
        BenefitInline,
        WhoIsForInline,
        ColorInline,
        SizeInline,
        MaterialInline,
        WeightInline,
        FlavorInline,
    ]

    fieldsets = (
        ("Información general", {
            "fields": ("id", "title", "short_description", "description", "keywords", "slug")
        }),
        ("Categorías", {
            "fields": ("category", "sub_category", "topic"),
        }),
        ("Multimedia", {
            "fields": ("images", "thumbnail", "thumbnail_preview")
        }),
        ("Precio y promociones", {
            "fields": ("price", "compare_price", "discount", "discount_until")
        }),
        ("Inventario y visibilidad", {
            "fields": ("stock", "hidden", "banned", "can_delete", "limited_edition")
        }),
        ("Detalles del producto", {
            "fields": ("condition", "packaging", "status")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at")
        }),
    )

    def status_badge(self, obj):
        if obj.status == 'draft':
            return format_html(
                '<span style="display:inline-flex;align-items:center;border-radius:9999px;background-color:#f9fafb;padding:2px 8px;font-size:12px;font-weight:500;color:#4b5563;border:1px solid rgba(107,114,128,0.1)">Draft</span>'
            )
        elif obj.status == 'published':
            return format_html(
                '<span style="display:inline-flex;align-items:center;border-radius:9999px;background-color:#ecfdf5;padding:2px 8px;font-size:12px;font-weight:500;color:#047857;border:1px solid rgba(5,150,105,0.2)">Published</span>'
            )
        else:
            return obj.status

    def save_model(self, request, obj, form, change):
        if not obj.slug:
            obj.slug = slugify(obj.title)
        super().save_model(request, obj, form, change)

    status_badge.short_description = 'Status'
    status_badge.allow_tags = True 


# --- Admins adicionales opcionales ---

@admin.register(ProductInteraction)
class ProductInteractionAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "interaction_type", "timestamp", "ip_address")
    list_filter = ("interaction_type", "interaction_category", "device_type", "day_of_week")
    search_fields = ("product__title", "user__email", "session_id", "ip_address", "product__slug")
    readonly_fields = ("timestamp", "product", "user", "session_id", "interaction_type", "interaction_category",
                       "rating", "review", "quantity", "total_price", "order_id",
                       "ip_address", "device_type", "hour_of_day", "day_of_week", "timestamp")

    fieldsets = (
        ("Identificación", {
            "fields": ("product", "user", "session_id")
        }),
        ("Tipo de interacción", {
            "fields": ("interaction_type", "interaction_category", "weight", "metadata")
        }),
        ("Datos contextuales", {
            "fields": ("rating", "review", "quantity", "total_price", "order_id")
        }),
        ("Trazabilidad", {
            "fields": ("ip_address", "device_type", "hour_of_day", "day_of_week", "timestamp")
        }),
    )


@admin.register(ProductAnalytics)
class ProductAnalyticsAdmin(admin.ModelAdmin):
    list_display = ("product", "impressions","views", "purchases", "conversion_rate", "revenue_generated")
    readonly_fields = [field.name for field in ProductAnalytics._meta.fields if field.name != "id"]
    search_fields = ("product__title", "product__id")

    fieldsets = (
        ("Producto", {
            "fields": ("product",)
        }),
        ("Tráfico General", {
            "fields": ("impressions", "clicks", "click_through_rate", "avg_time_on_page", "views", "first_viewed_at", "last_viewed_at")
        }),
        ("Interacciones Sociales", {
            "fields": ("likes", "shares", "wishlist_count")
        }),
        ("Carrito y Compras", {
            "fields": ("add_to_cart_count", "remove_from_cart_count", "purchases", "conversion_rate", "cart_abandonment_rate")
        }),
        ("Ingresos", {
            "fields": ("revenue_generated", "avg_order_value")
        }),
        ("Valoraciones", {
            "fields": ("average_rating", "review_count")
        }),
        ("Logística", {
            "fields": ("returns_count", "stockouts_count")
        }),
        ("Trazabilidad", {
            "fields": ("created_at", "updated_at")
        }),
    )