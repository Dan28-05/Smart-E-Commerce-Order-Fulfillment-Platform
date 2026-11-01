# mangementlogistics/orders/api/serializers.py
from rest_framework import serializers

from mangementlogistics.orders.constants import (
    OrderPaymentMethod,
    OrderPaymentStatus,
    OrderStatus,
)


class OrderUserSummarySerializer(serializers.Serializer):
    """
    Public summary of user associated with an order (customer or driver).
    """
    id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.CharField()
    phone_number = serializers.CharField(allow_null=True)


class OrderOutputSerializer(serializers.Serializer):
    """
    Full output serializer for an order.
    """
    id = serializers.IntegerField()
    tracking_number = serializers.CharField()
    customer = OrderUserSummarySerializer()
    driver = OrderUserSummarySerializer(allow_null=True)

    sender_name = serializers.CharField()
    sender_phone = serializers.CharField()
    sender_address = serializers.CharField()

    receiver_name = serializers.CharField()
    receiver_phone = serializers.CharField()
    receiver_address = serializers.CharField()

    weight = serializers.DecimalField(max_digits=8, decimal_places=2)
    item_description = serializers.CharField(allow_blank=True)
    notes = serializers.CharField(allow_blank=True)

    cod_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    shipping_fee = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)

    payment_method = serializers.CharField()
    payment_status = serializers.CharField()
    status = serializers.CharField()

    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    delivered_at = serializers.DateTimeField(allow_null=True)


class OrderCreateInputSerializer(serializers.Serializer):
    """
    Payload for creating a new delivery order.
    """
    sender_name = serializers.CharField(max_length=255)
    sender_phone = serializers.CharField(max_length=32)
    sender_address = serializers.CharField(max_length=500)

    receiver_name = serializers.CharField(max_length=255)
    receiver_phone = serializers.CharField(max_length=32)
    receiver_address = serializers.CharField(max_length=500)

    weight = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, default=1.0)
    item_description = serializers.CharField(required=False, default="", allow_blank=True)
    notes = serializers.CharField(required=False, default="", allow_blank=True)

    cod_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0.0)
    shipping_fee = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0.0)
    payment_method = serializers.ChoiceField(choices=OrderPaymentMethod.choices, default=OrderPaymentMethod.COD)

    # Optional fields for Admin
    customer_id = serializers.IntegerField(required=False, default=None, allow_null=True)
    driver_id = serializers.IntegerField(required=False, default=None, allow_null=True)


class OrderUpdateInputSerializer(serializers.Serializer):
    """
    Payload for updating an existing order.
    """
    sender_name = serializers.CharField(max_length=255, required=False)
    sender_phone = serializers.CharField(max_length=32, required=False)
    sender_address = serializers.CharField(max_length=500, required=False)

    receiver_name = serializers.CharField(max_length=255, required=False)
    receiver_phone = serializers.CharField(max_length=32, required=False)
    receiver_address = serializers.CharField(max_length=500, required=False)

    weight = serializers.DecimalField(max_digits=8, decimal_places=2, required=False)
    item_description = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    cod_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    shipping_fee = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    payment_method = serializers.ChoiceField(choices=OrderPaymentMethod.choices, required=False)
    payment_status = serializers.ChoiceField(choices=OrderPaymentStatus.choices, required=False)
    driver_id = serializers.IntegerField(required=False, allow_null=True)


class OrderStatusUpdateInputSerializer(serializers.Serializer):
    """
    Payload for updating order status and driver assignment.
    """
    status = serializers.ChoiceField(choices=OrderStatus.choices, required=True)
    driver_id = serializers.IntegerField(required=False, allow_null=True, default=None)


class OrderCancelInputSerializer(serializers.Serializer):
    """
    Payload for cancelling an order.
    """
    reason = serializers.CharField(required=False, default="", allow_blank=True)
