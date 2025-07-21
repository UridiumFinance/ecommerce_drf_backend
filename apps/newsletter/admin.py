from django.contrib import admin
from .models import NewsletterUser, Newsletter, ContactMessage


@admin.register(NewsletterUser)
class NewsletterUserAdmin(admin.ModelAdmin):
    list_display = ("email", "date_added")
    search_fields = ("email",)
    ordering = ("-date_added",)
    readonly_fields = ("date_added",)


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = ("name", "subject", "created")
    search_fields = ("name", "subject")
    list_filter = ("created",)
    date_hierarchy = "created"
    filter_horizontal = ("email",)
    readonly_fields = ("created",)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "phone_number", "created_at")
    search_fields = ("first_name", "last_name", "email", "phone_number", "message")
    list_filter = ("created_at",)
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)