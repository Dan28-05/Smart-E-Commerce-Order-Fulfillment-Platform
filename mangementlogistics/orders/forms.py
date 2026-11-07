# mangementlogistics/orders/forms.py
from django import forms

from mangementlogistics.orders.constants import (
    OrderPaymentMethod,
    OrderStatus,
    VIETNAM_PROVINCES,
)
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
    location = forms.CharField(
        required=False,
        label="Địa điểm / Bưu cục",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ví dụ: Kho phân loại Cầu Giấy"}),
    )
    note = forms.CharField(
        required=False,
        label="Ghi chú trạng thái",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ghi chú thêm tiến trình giao..."}),
    )
    driver = forms.ModelChoiceField(
        queryset=User.objects.filter(role=UserRole.DRIVER, is_active=True),
        required=False,
        label="Tài xế phụ trách",
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="-- Chưa phân công tài xế --",
    )


class OrderCheckpointForm(forms.Form):
    """
    Form for adding a transit checkpoint/milestone along the route.
    """
    location = forms.CharField(
        max_length=255,
        label="Vị trí / Bưu cục / Trạm trung chuyển",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Ví dụ: Bưu cục phát Tân Bình, TP.HCM"}
        ),
    )
    note = forms.CharField(
        label="Ghi chú tiến trình",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Ví dụ: Kiện hàng đã đến kho phát, chuẩn bị giao"}
        ),
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


class ShippingFeeEstimatorForm(forms.Form):
    """
    Form for estimating logistics delivery rates, SLAs, and insurance based on route and package size.
    """
    PROVINCE_CHOICES = [("", "-- Chọn Tỉnh / Thành phố --")] + [(p, p) for p in VIETNAM_PROVINCES]

    sender_province = forms.ChoiceField(
        choices=PROVINCE_CHOICES,
        label="Tỉnh / Thành phố gửi hàng",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_sender_province"}),
        initial="Hà Nội",
    )
    receiver_province = forms.ChoiceField(
        choices=PROVINCE_CHOICES,
        label="Tỉnh / Thành phố nhận hàng",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_receiver_province"}),
        initial="TP. Hồ Chí Minh",
    )
    weight = forms.DecimalField(
        min_value=0.01,
        initial=1.0,
        label="Trọng lượng thực tế (kg)",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "placeholder": "1.0", "id": "id_weight"}),
    )
    length = forms.DecimalField(
        min_value=0,
        required=False,
        initial=0,
        label="Chiều dài (cm)",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "1", "placeholder": "Dài (cm)", "id": "id_length"}),
    )
    width = forms.DecimalField(
        min_value=0,
        required=False,
        initial=0,
        label="Chiều rộng (cm)",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "1", "placeholder": "Rộng (cm)", "id": "id_width"}),
    )
    height = forms.DecimalField(
        min_value=0,
        required=False,
        initial=0,
        label="Chiều cao (cm)",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "1", "placeholder": "Cao (cm)", "id": "id_height"}),
    )
    cod_amount = forms.DecimalField(
        min_value=0,
        required=False,
        initial=0,
        label="Tiền thu hộ COD / Khai giá (VNĐ)",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "10000", "placeholder": "0", "id": "id_cod_amount"}),
    )


class CODReconciliationGenerateForm(forms.Form):
    """
    Form to trigger generation of a new COD reconciliation statement.
    """
    customer = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        label="Khách hàng / Chủ Shop",
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="-- Chọn khách hàng --",
    )
    notes = forms.CharField(
        required=False,
        label="Ghi chú kỳ đối soát",
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 3, "placeholder": "Ví dụ: Đối soát định kỳ tuần 1 tháng 11..."}
        ),
    )

    def __init__(self, *args, user: User | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        is_admin = user and (user.is_superuser or getattr(user, "role", None) == UserRole.ADMIN)
        if not is_admin:
            self.fields.pop("customer", None)
        else:
            self.fields["customer"].required = True
            self.fields["customer"].queryset = User.objects.filter(
                role=UserRole.CUSTOMER, is_active=True
            ).order_by("name", "email")


class CODReconciliationProcessForm(forms.Form):
    """
    Form for administrators to confirm or mark paid on a reconciliation statement.
    """
    ACTION_CHOICES = [
        ("CONFIRM", "Xác nhận đối soát (Chuyển sang Đã xác nhận)"),
        ("MARK_PAID", "Quyết toán / Chuyển khoản (Chuyển sang Đã thanh toán)"),
    ]
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        label="Hành động xử lý",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    notes = forms.CharField(
        required=False,
        label="Ghi chú xử lý / Mã giao dịch ngân hàng",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Ví dụ: Mã GD VCB 987654321..."}
        ),
    )


