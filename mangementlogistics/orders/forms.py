# mangementlogistics/orders/forms.py
from django import forms

from mangementlogistics.orders.constants import OrderPaymentMethod, OrderStatus
from mangementlogistics.orders.models import Order
from mangementlogistics.users.constants import UserRole
from mangementlogistics.users.models import User


class OrderCreateForm(forms.ModelForm):
    """
    Form for customers or admins to create a new delivery order.
    """
    class Meta:
        model = Order
        fields = [
            "sender_name",
            "sender_phone",
            "sender_address",
            "receiver_name",
            "receiver_phone",
            "receiver_address",
            "weight",
            "item_description",
            "notes",
            "cod_amount",
            "shipping_fee",
            "payment_method",
        ]
        labels = {
            "sender_name": "Tên người gửi",
            "sender_phone": "Số điện thoại người gửi",
            "sender_address": "Địa chỉ gửi hàng",
            "receiver_name": "Tên người nhận",
            "receiver_phone": "Số điện thoại người nhận",
            "receiver_address": "Địa chỉ nhận hàng",
            "weight": "Trọng lượng (kg)",
            "item_description": "Mô tả hàng hóa",
            "notes": "Ghi chú cho tài xế",
            "cod_amount": "Tiền thu hộ COD (VNĐ)",
            "shipping_fee": "Cước phí vận chuyển (VNĐ)",
            "payment_method": "Phương thức thanh toán",
        }
        widgets = {
            "sender_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ví dụ: Nguyễn Văn A"}),
            "sender_phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "0912345678"}),
            "sender_address": forms.TextInput(attrs={"class": "form-control", "placeholder": "Số nhà, tên đường, phường, quận, thành phố"}),
            "receiver_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ví dụ: Trần Thị B"}),
            "receiver_phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "0987654321"}),
            "receiver_address": forms.TextInput(attrs={"class": "form-control", "placeholder": "Địa chỉ chi tiết người nhận"}),
            "weight": forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "min": "0.01"}),
            "item_description": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Quần áo, tài liệu, linh kiện điện tử..."}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Giao giờ hành chính, gọi trước khi đến..."}),
            "cod_amount": forms.NumberInput(attrs={"class": "form-control", "step": "1000", "min": "0"}),
            "shipping_fee": forms.NumberInput(attrs={"class": "form-control", "step": "1000", "min": "0"}),
            "payment_method": forms.Select(attrs={"class": "form-select"}),
        }


class OrderUpdateForm(forms.ModelForm):
    """
    Form for editing an order details.
    """
    class Meta:
        model = Order
        fields = [
            "sender_name",
            "sender_phone",
            "sender_address",
            "receiver_name",
            "receiver_phone",
            "receiver_address",
            "weight",
            "item_description",
            "notes",
            "cod_amount",
            "shipping_fee",
            "payment_method",
        ]
        widgets = {
            "sender_name": forms.TextInput(attrs={"class": "form-control"}),
            "sender_phone": forms.TextInput(attrs={"class": "form-control"}),
            "sender_address": forms.TextInput(attrs={"class": "form-control"}),
            "receiver_name": forms.TextInput(attrs={"class": "form-control"}),
            "receiver_phone": forms.TextInput(attrs={"class": "form-control"}),
            "receiver_address": forms.TextInput(attrs={"class": "form-control"}),
            "weight": forms.NumberInput(attrs={"class": "form-control", "step": "0.1"}),
            "item_description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "cod_amount": forms.NumberInput(attrs={"class": "form-control", "step": "1000"}),
            "shipping_fee": forms.NumberInput(attrs={"class": "form-control", "step": "1000"}),
            "payment_method": forms.Select(attrs={"class": "form-select"}),
        }


class OrderStatusUpdateForm(forms.Form):
    """
    Form for admins or drivers to update order delivery status and assign driver.
    """
    status = forms.ChoiceField(
        choices=OrderStatus.choices,
        label="Trạng thái đơn hàng",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    driver = forms.ModelChoiceField(
        queryset=User.objects.filter(role=UserRole.DRIVER, is_active=True),
        required=False,
        label="Tài xế phụ trách",
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="-- Chưa phân công tài xế --",
    )


class OrderCancelForm(forms.Form):
    """
    Form for entering cancellation reason.
    """
    reason = forms.CharField(
        label="Lý do hủy đơn",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Nhập lý do bạn muốn hủy đơn hàng này..."}),
    )
