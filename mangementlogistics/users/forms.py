from django import forms

from mangementlogistics.users.constants import UserRole
from mangementlogistics.users.exceptions import DuplicateEmailError
from mangementlogistics.users.models import User
from mangementlogistics.users.services import user_create


class UserCreateForm(forms.ModelForm):
    password = forms.CharField(
        label="Mật khẩu",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Nhập mật khẩu (tối thiểu 6 ký tự)"}),
        min_length=6,
    )

    class Meta:
        model = User
        fields = ["name", "email", "password", "role", "phone_number", "address"]
        labels = {
            "name": "Họ và tên",
            "email": "Địa chỉ Email",
            "role": "Vai trò",
            "phone_number": "Số điện thoại",
            "address": "Địa chỉ",
        }
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ví dụ: Nguyễn Văn A"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "example@email.com"}),
            "role": forms.Select(attrs={"class": "form-select"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "0912345678"}),
            "address": forms.TextInput(attrs={"class": "form-control", "placeholder": "Số nhà, tên đường, thành phố"}),
        }

    def save(self, commit=True):
        cleaned_data = self.cleaned_data
        try:
            return user_create(
                name=cleaned_data.get("name", ""),
                email=cleaned_data["email"],
                password=cleaned_data["password"],
                role=cleaned_data.get("role", UserRole.CUSTOMER),
                phone_number=cleaned_data.get("phone_number") or None,
                address=cleaned_data.get("address") or None,
            )
        except DuplicateEmailError as exc:
            self.add_error("email", str(exc))
            raise forms.ValidationError(str(exc))
