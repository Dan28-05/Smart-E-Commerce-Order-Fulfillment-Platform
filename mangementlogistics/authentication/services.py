# mangementlogistics/authentication/services.py
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken, UntypedToken

from mangementlogistics.authentication.exceptions import (
    InactiveAccountError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from mangementlogistics.authentication.validators import validate_password_complexity
from mangementlogistics.users.exceptions import InvalidPasswordError
from mangementlogistics.users.services import user_change_password

User = get_user_model()


def auth_get_jwt_pair(*, user: User) -> dict[str, str]:
    """
    Generate JWT access and refresh token pair for a user with custom claims.
    """
    refresh = RefreshToken.for_user(user)

    # Attach custom claims into JWT payload
    refresh["email"] = user.email
    refresh["role"] = getattr(user, "role", "")
    refresh["name"] = getattr(user, "name", "")

    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


def auth_login_with_credentials(*, email: str, password: str) -> tuple[User, dict[str, str]]:
    """
    Authenticates a user with email and password, returning user and JWT token pair.
    """
    user = User.objects.filter(email__iexact=email).first()

    if not user or not user.check_password(password):
        raise InvalidCredentialsError("Email hoặc mật khẩu không chính xác.")

    if not user.is_active:
        raise InactiveAccountError("Tài khoản đã bị khóa hoặc ngừng hoạt động.")

    update_last_login(None, user)
    tokens = auth_get_jwt_pair(user=user)

    return user, tokens


def auth_refresh_access_token(*, refresh_token: str) -> str:
    """
    Validates a refresh token and returns a newly issued access token.
    """
    try:
        refresh = RefreshToken(refresh_token)
        return str(refresh.access_token)
    except (InvalidToken, TokenError) as exc:
        raise InvalidTokenError(f"Refresh token không hợp lệ hoặc đã hết hạn: {exc}") from exc


def auth_verify_token(*, token: str) -> None:
    """
    Validates if an access or refresh token is structurally and cryptographically valid.
    """
    try:
        UntypedToken(token)
    except (InvalidToken, TokenError) as exc:
        raise InvalidTokenError(f"Token không hợp lệ hoặc đã hết hạn: {exc}") from exc


def auth_blacklist_token(*, refresh_token: str) -> None:
    """
    Attempts to blacklist a refresh token if simplejwt blacklist app is available.
    """
    try:
        token = RefreshToken(refresh_token)
        if hasattr(token, "blacklist"):
            token.blacklist()
    except (InvalidToken, TokenError) as exc:
        raise InvalidTokenError(f"Không thể thu hồi token: {exc}") from exc


def auth_change_password(
    *,
    user: User,
    old_password: str,
    new_password: str,
    new_password_confirm: str,
) -> User:
    """
    Verifies old password, password match and complexity constraints before changing password.
    """
    return user_change_password(
        user=user,
        old_password=old_password,
        new_password=new_password,
        new_password_confirm=new_password_confirm,
    )


def auth_password_reset_request(*, email: str, base_url: str | None = None) -> tuple[bool, str]:
    """
    Sends password reset email containing secure reset token and link to the user.
    Protects user privacy by always returning a generic success message.
    """
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    message = "Nếu email tồn tại trong hệ thống, hướng dẫn đặt lại mật khẩu đã được gửi đến email của bạn."

    if not user:
        return True, message

    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    domain = base_url.rstrip("/") if base_url else "http://localhost:8000"
    reset_url = f"{domain}/users/password/reset/confirm/{uidb64}/{token}/"

    subject = "[Management Logistics] Yêu cầu đặt lại mật khẩu"
    body = f"""Xin chào {user.name or user.email},

Bạn (hoặc ai đó) vừa yêu cầu đặt lại mật khẩu cho tài khoản trên hệ thống Management Logistics.

Để tạo mật khẩu mới, vui lòng truy cập đường dẫn dưới đây:
{reset_url}

Nếu bạn sử dụng ứng dụng di động hoặc API, bạn có thể sử dụng thông tin sau:
- UID: {uidb64}
- Token: {token}

Lưu ý:
- Liên kết này chỉ có hiệu lực một lần và sẽ hết hạn sau thời gian quy định.
- Nếu bạn không gửi yêu cầu này, vui lòng bỏ qua email. Mật khẩu hiện tại của bạn vẫn an toàn.

Trân trọng,
Đội ngũ Management Logistics
"""
    html_body = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; padding: 24px;">
        <h2 style="color: #0d6efd; margin-top: 0;">Management Logistics</h2>
        <p>Xin chào <strong>{user.name or user.email}</strong>,</p>
        <p>Bạn (hoặc ai đó) vừa yêu cầu đặt lại mật khẩu cho tài khoản trên hệ thống của chúng tôi.</p>
        <div style="text-align: center; margin: 28px 0;">
            <a href="{reset_url}" style="background-color: #0d6efd; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                Đặt lại mật khẩu
            </a>
        </div>
        <p style="font-size: 14px; color: #666;">
            Nếu nút bấm không hoạt động, bạn có thể sao chép liên kết sau dán vào trình duyệt:<br>
            <a href="{reset_url}" style="color: #0d6efd; word-break: break-all;">{reset_url}</a>
        </p>
        <div style="background-color: #f8f9fa; border-radius: 6px; padding: 12px; margin-top: 16px; font-size: 13px;">
            <strong>Thông tin dành cho API / Mobile:</strong><br>
            - UID: <code>{uidb64}</code><br>
            - Token: <code>{token}</code>
        </div>
        <hr style="border: 0; border-top: 1px solid #eee; margin: 24px 0;">
        <p style="font-size: 12px; color: #999;">
            Nếu bạn không gửi yêu cầu này, vui lòng bỏ qua email. Mật khẩu của bạn vẫn an toàn.<br>
            Email này được gửi tự động, vui lòng không phản hồi.
        </p>
    </div>
    """

    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_body,
        fail_silently=False,
    )

    return True, message


def auth_password_reset_validate_token(*, uidb64: str, token: str) -> User:
    """
    Validates password reset UID and token, returning the user if valid.
    """
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.filter(pk=uid, is_active=True).first()
    except (TypeError, ValueError, OverflowError):
        user = None

    if user is None:
        raise InvalidTokenError("Liên kết đặt lại mật khẩu không hợp lệ hoặc người dùng không tồn tại.")

    if not default_token_generator.check_token(user, token):
        raise InvalidTokenError("Mã token đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.")

    return user


def auth_password_reset_confirm(
    *,
    uidb64: str,
    token: str,
    new_password: str,
    new_password_confirm: str,
) -> User:
    """
    Resets the password after verifying token and constraints.
    """
    if new_password != new_password_confirm:
        raise InvalidPasswordError("Mật khẩu xác nhận không khớp!")

    validate_password_complexity(new_password)

    user = auth_password_reset_validate_token(uidb64=uidb64, token=token)

    if user.check_password(new_password):
        raise InvalidPasswordError("Mật khẩu mới không được trùng với mật khẩu hiện tại!")

    user.set_password(new_password)
    user.save()
    return user
