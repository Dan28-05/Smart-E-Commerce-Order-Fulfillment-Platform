# mangementlogistics/orders/admin.py
from django.contrib import admin

from mangementlogistics.orders.models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "tracking_number",
        "customer",
        "receiver_name",
        "receiver_phone",
        "status",
        "cod_amount",
        "shipping_fee",
        "driver",
        "created_at",
    )
    list_filter = ("status", "payment_method", "payment_status", "created_at")
    search_fields = (
        "tracking_number",
        "sender_name",
        "sender_phone",
        "receiver_name",
        "receiver_phone",
        "customer__email",
        "driver__email",
    )
    readonly_fields = ("tracking_number", "created_at", "updated_at", "delivered_at")
