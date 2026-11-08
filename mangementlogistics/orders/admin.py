# mangementlogistics/orders/admin.py
from django.contrib import admin

from mangementlogistics.orders.models import (
    CODReconciliation,
    Order,
    OrderReturn,
    OrderTrackingHistory,
)


class OrderTrackingHistoryInline(admin.TabularInline):
    model = OrderTrackingHistory
    extra = 0
    readonly_fields = ("created_at",)
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderTrackingHistoryInline]
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


@admin.register(OrderTrackingHistory)
class OrderTrackingHistoryAdmin(admin.ModelAdmin):
    list_display = ("order", "status", "location", "actor", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("order__tracking_number", "location", "note")
    readonly_fields = ("created_at",)


@admin.register(CODReconciliation)
class CODReconciliationAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "customer",
        "total_orders_count",
        "total_cod_amount",
        "total_shipping_fees",
        "net_payout_amount",
        "status",
        "created_at",
        "paid_at",
    )
    list_filter = ("status", "created_at", "paid_at")
    search_fields = ("code", "customer__email", "customer__name")
    readonly_fields = ("code", "created_at", "confirmed_at", "paid_at")


@admin.register(OrderReturn)
class OrderReturnAdmin(admin.ModelAdmin):
    list_display = (
        "return_code",
        "order",
        "requested_by",
        "reason",
        "status",
        "fee_payer",
        "return_shipping_fee",
        "refund_amount",
        "assigned_driver",
        "created_at",
    )
    list_filter = ("status", "reason", "fee_payer", "created_at")
    search_fields = (
        "return_code",
        "order__tracking_number",
        "requested_by__email",
        "assigned_driver__email",
    )
    readonly_fields = ("return_code", "created_at", "approved_at", "completed_at", "updated_at")



