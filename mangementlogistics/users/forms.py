# mangementlogistics/users/forms.py
from django import forms

from mangementlogistics.authentication.validators import validate_password_complexity
from mangementlogistics.users.constants import UserRole
from mangementlogistics.users.exceptions import DuplicateEmailError, InvalidPasswordError
from mangementlogistics.users.models import User
from mangementlogistics.users.services import user_change_password, user_create


class UserCreateForm(forms.ModelForm):
    password = forms.CharField(
        label="Mật khẩu",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Tối thiểu 8 ký tự, có chữ hoa, chữ thường, số và ký tự đặc biệt",
            }
        ),
        min_length=8,
        help_text="Mật khẩu phải chứa ít nhất 8 ký tự, bao gồm chữ hoa, chữ thường, số và ký tự đặc biệt (!@#$...).",
    )
    password_confirm = forms.CharField(
        label="Xác nhận mật khẩu",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Nhập lại mật khẩu"}),
        min_length=8,
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

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            self.add_error("password_confirm", "Mật khẩu xác nhận không khớp.")

        if password:
            try:
                validate_password_complexity(password)
            except InvalidPasswordError as exc:
                self.add_error("password", str(exc))

        return cleaned_data

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
        except (DuplicateEmailError, InvalidPasswordError) as exc:
            self.add_error(None, str(exc))
            raise forms.ValidationError(str(exc))


class UserPasswordChangeForm(forms.Form):
    """
    Form for authenticated users to change their password.
    """
    old_password = forms.CharField(
        label="Mật khẩu hiện tại",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Nhập mật khẩu hiện tại"}),
    )
    new_password = forms.CharField(
        label="Mật khẩu mới",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Tối thiểu 8 ký tự, có chữ hoa, thường, số, ký tự đặc biệt",
            }
        ),
        min_length=8,
        help_text="Tối thiểu 8 ký tự, bao gồm ít nhất 1 chữ hoa, 1 chữ thường, 1 số và 1 ký tự đặc biệt.",
    )
    new_password_confirm = forms.CharField(
        label="Xác nhận mật khẩu mới",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Nhập lại mật khẩu mới"}),
        min_length=8,
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        old_password = cleaned_data.get("old_password")
        new_password = cleaned_data.get("new_password")
        new_password_confirm = cleaned_data.get("new_password_confirm")

        if old_password and not self.user.check_password(old_password):
            self.add_error("old_password", "Mật khẩu hiện tại không chính xác.")

        if new_password and new_password_confirm and new_password != new_password_confirm:
            self.add_error("new_password_confirm", "Mật khẩu xác nhận không khớp.")

        if old_password and new_password and old_password == new_password:
            self.add_error("new_password", "Mật khẩu mới không được trùng với mật khẩu cũ.")

        if new_password:
            try:
                validate_password_complexity(new_password)
            except InvalidPasswordError as exc:
                self.add_error("new_password", str(exc))

        return cleaned_data

    def save(self):
        cleaned_data = self.cleaned_data
        return user_change_password(
            user=self.user,
            old_password=cleaned_data["old_password"],
            new_password=cleaned_data["new_password"],
            new_password_confirm=cleaned_data["new_password_confirm"],
        )


class PasswordResetRequestForm(forms.Form):
    """
    Form to request a password reset email.
    """
    email = forms.EmailField(
        label="Địa chỉ Email",
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "Nhập email tài khoản của bạn"}),
        help_text="Chúng tôi sẽ gửi một liên kết đặt lại mật khẩu đến email này.",
    )


class PasswordResetConfirmForm(forms.Form):
    """
    Form to enter new password after verifying token.
    """
    new_password = forms.CharField(
        label="Mật khẩu mới",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Tối thiểu 8 ký tự, có hoa, thường, số, ký tự đặc biệt",
            }
        ),
        min_length=8,
        help_text="Tối thiểu 8 ký tự, bao gồm ít nhất 1 chữ hoa, 1 chữ thường, 1 số và 1 ký tự đặc biệt.",
    )
    new_password_confirm = forms.CharField(
        label="Xác nhận mật khẩu mới",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Nhập lại mật khẩu mới"}),
        min_length=8,
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        new_password_confirm = cleaned_data.get("new_password_confirm")

        if new_password and new_password_confirm and new_password != new_password_confirm:
            self.add_error("new_password_confirm", "Mật khẩu xác nhận không khớp.")

        if new_password:
            try:
                validate_password_complexity(new_password)
            except InvalidPasswordError as exc:
                self.add_error("new_password", str(exc))

        return cleaned_data


class UserLoginForm(forms.Form):
    """
    Form for user authentication in the web UI.
    """
    email = forms.EmailField(
        label="Địa chỉ Email",
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "name@example.com", "autofocus": True}
        ),
    )
    password = forms.CharField(
        label="Mật khẩu",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Nhập mật khẩu"}
        ),
    )
    remember_me = forms.BooleanField(
        label="Ghi nhớ đăng nhập",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


class UserProfileUpdateForm(forms.ModelForm):
    """
    Form for authenticated users to update their personal profile information.
    """
    class Meta:
        model = User
        fields = ["name", "phone_number", "address"]
        labels = {
            "name": "Họ và tên",
            "phone_number": "Số điện thoại liên hệ",
            "address": "Địa chỉ mặc định",
        }
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ví dụ: Nguyễn Văn A"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ví dụ: 0912345678"}),
            "address": forms.TextInput(attrs={"class": "form-control", "placeholder": "Số nhà, tên đường, phường, quận, thành phố"}),
        }

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number")
        if phone:
            phone = phone.strip()
            # Ensure unique phone number except for current user
            if User.objects.filter(phone_number=phone).exclude(id=self.instance.id).exists():
                raise forms.ValidationError("Số điện thoại này đã được sử dụng bởi một tài khoản khác.")
        return phone


