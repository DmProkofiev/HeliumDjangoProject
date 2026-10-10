from django.contrib import admin
from .models import Payment, Order, Transaction

class OrderInline(admin.TabularInline):
    model = Order
    extra = 0
    fields = ('title', 'executor', 'amount', 'status')
    readonly_fields = ('title', 'executor', 'amount', 'status')
    can_delete = False

class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    fields = ('type', 'amount', 'status', 'external_id', 'created_at')
    readonly_fields = ('type', 'amount', 'status', 'external_id', 'created_at')
    can_delete = False

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('customer__username', 'payment_id')
    inlines = [OrderInline, TransactionInline]

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'customer', 'executor', 'amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'customer__username', 'executor__username')
    inlines = [TransactionInline]

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'amount', 'status', 'payment', 'order', 'created_at')
    list_filter = ('type', 'status')
    search_fields = ('external_id',)