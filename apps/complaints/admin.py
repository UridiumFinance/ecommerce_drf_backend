from django.contrib import admin
from .models import Complaint

@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'last_names', 'email', 'selected_application', 'selected_method', "status", 'created_at')
    search_fields = ('full_name', 'last_names', 'email', 'identification', 'telephone', 'city', 'state', 'country')
    list_filter = ('selected_application', 'selected_method')

    def created_at(self, obj):
        return obj._state.db.creation_counter

    created_at.admin_order_field = '_state.db.creation_counter'
    created_at.short_description = 'Created At'
