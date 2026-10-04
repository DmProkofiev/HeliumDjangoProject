from django.contrib import admin
from .models import Order, Transaction

class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    readonly_fields = ('type', 'status', 'amount', 'external_id', 'idempotence_key', 'created_at')
    can_delete = False

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'customer', 'executor', 'amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'customer__username', 'executor__username')
    readonly_fields = ('payment_id', 'created_at', 'updated_at')
    inlines = [TransactionInline]

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'type', 'amount', 'status', 'created_at')
    list_filter = ('type', 'status')
    search_fields = ('external_id',)