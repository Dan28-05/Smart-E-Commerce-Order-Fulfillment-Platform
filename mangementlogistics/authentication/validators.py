# mangementlogistics/authentication/validators.py
import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from mangementlogistics.users.exceptions import InvalidPasswordError


def validate_password_complexity(password: str) -> None:
    """
    Ràng buộc mật khẩu:
    - Độ dài tối thiểu 8 ký tự.
    - Chứa ít nhất 1 ký tự in hoa (A-Z).
    - Chứa ít nhất 1 ký tự in thường (a-z).
    - Chứa ít nhất 1 chữ số (0-9).
    - Chứa ít nhất 1 ký tự đặc biệt (ví dụ: !@#$%^&*...).
    """
    errors = []

    if len(password) < 8:
        errors.append("Mật khẩu phải có ít nhất 8 ký tự.")

    if not re.search(r"[A-Z]", password):
        errors.append("Mật khẩu phải chứa ít nhất 1 chữ cái in hoa (A-Z).")

    if not re.search(r"[a-z]", password):
        errors.append("Mật khẩu phải chứa ít nhất 1 chữ cái in thường (a-z).")

    if not re.search(r"\d", password):
        errors.append("Mật khẩu phải chứa ít nhất 1 chữ số (0-9).")

    if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?/~`]", password):
        errors.append("Mật khẩu phải chứa ít nhất 1 ký tự đặc biệt (!@#$%^&*...).")

    if errors:
        raise InvalidPasswordError(" ".join(errors))


class ComplexityPasswordValidator:
    """
    Django password validator tích hợp vào AUTH_PASSWORD_VALIDATORS.
    """

    def validate(self, password, user=None):
        try:
            validate_password_complexity(password)
        except InvalidPasswordError as exc:
            raise ValidationError(str(exc)) from exc

    def get_help_text(self):
        return _(
            "Mật khẩu phải có tối thiểu 8 ký tự, bao gồm ít nhất 1 chữ cái in hoa, "
            "1 chữ cái in thường, 1 chữ số và 1 ký tự đặc biệt."
        )

