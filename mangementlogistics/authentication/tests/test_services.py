# mangementlogistics/authentication/tests/test_services.py
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
import pytest
from rest_framework_simplejwt.tokens import AccessToken

from mangementlogistics.authentication.exceptions import (
    InactiveAccountError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from mangementlogistics.authentication.services import (
    auth_change_password,
    auth_get_jwt_pair,
    auth_login_with_credentials,
    auth_password_reset_confirm,
    auth_password_reset_request,
    auth_password_reset_validate_token,
    auth_refresh_access_token,
    auth_verify_token,
)
from mangementlogistics.authentication.validators import validate_password_complexity
from mangementlogistics.users.constants import UserRole
from mangementlogistics.users.exceptions import InvalidPasswordError
from mangementlogistics.users.models import User

pytestmark = pytest.mark.django_db


# --- JWT Token & Login Tests ---


def test_auth_get_jwt_pair():
    user = User.objects.create_user(
        username="driver@example.com",
        email="driver@example.com",
        password="ValidPassword123!",
        name="John Driver",
        role=UserRole.DRIVER,
    )
    tokens = auth_get_jwt_pair(user=user)

    assert "access" in tokens
    assert "refresh" in tokens

    access_token = AccessToken(tokens["access"])
    assert access_token["email"] == "driver@example.com"
    assert access_token["role"] == UserRole.DRIVER
    assert access_token["name"] == "John Driver"


def test_auth_login_with_credentials_success():
    User.objects.create_user(
        username="user@example.com",
        email="user@example.com",
        password="ValidPassword123!",
        name="Test User",
        role=UserRole.CUSTOMER,
    )

    user, tokens = auth_login_with_credentials(
        email="user@example.com",
        password="ValidPassword123!",
    )

    assert user.email == "user@example.com"
    assert tokens["access"] is not None
    assert tokens["refresh"] is not None
    assert user.last_login is not None


def test_auth_login_invalid_password():
    User.objects.create_user(
        username="user@example.com",
        email="user@example.com",
        password="ValidPassword123!",
    )

    with pytest.raises(InvalidCredentialsError):
        auth_login_with_credentials(
            email="user@example.com",
            password="wrongpassword",
        )


def test_auth_login_nonexistent_email():
    with pytest.raises(InvalidCredentialsError):
        auth_login_with_credentials(
            email="nonexistent@example.com",
            password="anypassword",
        )


def test_auth_login_inactive_user():
    user = User.objects.create_user(
        username="inactive@example.com",
        email="inactive@example.com",
        password="ValidPassword123!",
        is_active=False,
    )

    with pytest.raises(InactiveAccountError):
        auth_login_with_credentials(
            email="inactive@example.com",
            password="ValidPassword123!",
        )


def test_auth_refresh_access_token():
    user = User.objects.create_user(
        username="refresh@example.com",
        email="refresh@example.com",
        password="ValidPassword123!",
    )
    tokens = auth_get_jwt_pair(user=user)

    new_access_token = auth_refresh_access_token(refresh_token=tokens["refresh"])
    assert new_access_token is not None
    assert isinstance(new_access_token, str)


def test_auth_refresh_invalid_token():
    with pytest.raises(InvalidTokenError):
        auth_refresh_access_token(refresh_token="invalid.refresh.token")


def test_auth_verify_token_success_and_failure():
    user = User.objects.create_user(
        username="verify@example.com",
        email="verify@example.com",
        password="ValidPassword123!",
    )
    tokens = auth_get_jwt_pair(user=user)

    auth_verify_token(token=tokens["access"])

    with pytest.raises(InvalidTokenError):
        auth_verify_token(token="invalid-token")


# --- Password Complexity Validator Tests ---


def test_validate_password_complexity():
    # Valid password
    validate_password_complexity("StrongP@ssw0rd")

    # Too short (< 8 chars)
    with pytest.raises(InvalidPasswordError, match="ít nhất 8 ký tự"):
        validate_password_complexity("Short1!")

    # Missing uppercase
    with pytest.raises(InvalidPasswordError, match="chữ cái in hoa"):
        validate_password_complexity("nouppercase123!")

    # Missing lowercase
    with pytest.raises(InvalidPasswordError, match="chữ cái in thường"):
        validate_password_complexity("NOLOWERCASE123!")

    # Missing digit
    with pytest.raises(InvalidPasswordError, match="chữ số"):
        validate_password_complexity("NoDigitsHere!@#")

    # Missing special character
    with pytest.raises(InvalidPasswordError, match="ký tự đặc biệt"):
        validate_password_complexity("NoSpecialChar123")


# --- Change Password Tests ---


def test_auth_change_password_success():
    user = User.objects.create_user(
        username="change_pwd@example.com",
        email="change_pwd@example.com",
        password="OldP@ssword123",
    )

    updated_user = auth_change_password(
        user=user,
        old_password="OldP@ssword123",
        new_password="NewP@ssword456!",
        new_password_confirm="NewP@ssword456!",
    )

    assert updated_user.check_password("NewP@ssword456!")
    assert not updated_user.check_password("OldP@ssword123")


def test_auth_change_password_wrong_old_password():
    user = User.objects.create_user(
        username="change_pwd_err@example.com",
        email="change_pwd_err@example.com",
        password="OldP@ssword123",
    )

    with pytest.raises(InvalidPasswordError, match="Mật khẩu cũ không chính xác"):
        auth_change_password(
            user=user,
            old_password="WrongPassword123!",
            new_password="NewP@ssword456!",
            new_password_confirm="NewP@ssword456!",
        )


def test_auth_change_password_mismatch_confirm():
    user = User.objects.create_user(
        username="mismatch@example.com",
        email="mismatch@example.com",
        password="OldP@ssword123",
    )

    with pytest.raises(InvalidPasswordError, match="Mật khẩu xác nhận không khớp"):
        auth_change_password(
            user=user,
            old_password="OldP@ssword123",
            new_password="NewP@ssword456!",
            new_password_confirm="DifferentPassword456!",
        )


def test_auth_change_password_same_as_old():
    user = User.objects.create_user(
        username="same_pwd@example.com",
        email="same_pwd@example.com",
        password="OldP@ssword123",
    )

    with pytest.raises(InvalidPasswordError, match="không được trùng với mật khẩu cũ"):
        auth_change_password(
            user=user,
            old_password="OldP@ssword123",
            new_password="OldP@ssword123",
            new_password_confirm="OldP@ssword123",
        )


# --- Password Reset via Email Tests ---


def test_auth_password_reset_request_sends_email():
    mail.outbox = []
    user = User.objects.create_user(
        username="reset_me@example.com",
        email="reset_me@example.com",
        password="InitialPassword123!",
        name="Reset User",
    )

    success, message = auth_password_reset_request(email="reset_me@example.com")
    assert success is True
    assert len(mail.outbox) == 1

    sent_mail = mail.outbox[0]
    assert sent_mail.to == ["reset_me@example.com"]
    assert "Yêu cầu đặt lại mật khẩu" in sent_mail.subject
    assert "UID:" in sent_mail.body
    assert "Token:" in sent_mail.body


def test_auth_password_reset_validate_and_confirm():
    user = User.objects.create_user(
        username="confirm_me@example.com",
        email="confirm_me@example.com",
        password="InitialPassword123!",
    )

    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    # 1. Validate token
    validated_user = auth_password_reset_validate_token(uidb64=uidb64, token=token)
    assert validated_user.id == user.id

    # 2. Confirm reset
    updated_user = auth_password_reset_confirm(
        uidb64=uidb64,
        token=token,
        new_password="BrandNewPassword123!",
        new_password_confirm="BrandNewPassword123!",
    )

    assert updated_user.check_password("BrandNewPassword123!")

    # 3. Token cannot be reused
    with pytest.raises(InvalidTokenError):
        auth_password_reset_validate_token(uidb64=uidb64, token=token)
