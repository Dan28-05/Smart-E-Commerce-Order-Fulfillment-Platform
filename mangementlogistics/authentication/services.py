# mangementlogistics/authentication/services.py
from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken, UntypedToken

from mangementlogistics.authentication.exceptions import (
    InactiveAccountError,
    InvalidCredentialsError,
    InvalidTokenError,
)

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
