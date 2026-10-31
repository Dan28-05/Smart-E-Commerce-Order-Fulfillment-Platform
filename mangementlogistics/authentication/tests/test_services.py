# mangementlogistics/authentication/tests/test_services.py
import pytest
from rest_framework_simplejwt.tokens import AccessToken

from mangementlogistics.authentication.exceptions import (
    InactiveAccountError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from mangementlogistics.authentication.services import (
    auth_get_jwt_pair,
    auth_login_with_credentials,
    auth_refresh_access_token,
    auth_verify_token,
)
from mangementlogistics.users.constants import UserRole
from mangementlogistics.users.models import User

pytestmark = pytest.mark.django_db


def test_auth_get_jwt_pair():
    user = User.objects.create_user(
        username="driver@example.com",
        email="driver@example.com",
        password="secretpassword123",
        name="John Driver",
        role=UserRole.DRIVER,
    )
    tokens = auth_get_jwt_pair(user=user)

    assert "access" in tokens
    assert "refresh" in tokens

    # Decode and verify custom claims in access token
    access_token = AccessToken(tokens["access"])
    assert access_token["email"] == "driver@example.com"
    assert access_token["role"] == UserRole.DRIVER
    assert access_token["name"] == "John Driver"


def test_auth_login_with_credentials_success():
    User.objects.create_user(
        username="user@example.com",
        email="user@example.com",
        password="strongpassword",
        name="Test User",
        role=UserRole.CUSTOMER,
    )

    user, tokens = auth_login_with_credentials(
        email="user@example.com",
        password="strongpassword",
    )

    assert user.email == "user@example.com"
    assert tokens["access"] is not None
    assert tokens["refresh"] is not None
    assert user.last_login is not None


def test_auth_login_invalid_password():
    User.objects.create_user(
        username="user@example.com",
        email="user@example.com",
        password="strongpassword",
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
        password="strongpassword",
        is_active=False,
    )

    with pytest.raises(InactiveAccountError):
        auth_login_with_credentials(
            email="inactive@example.com",
            password="strongpassword",
        )


def test_auth_refresh_access_token():
    user = User.objects.create_user(
        username="refresh@example.com",
        email="refresh@example.com",
        password="strongpassword",
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
        password="strongpassword",
    )
    tokens = auth_get_jwt_pair(user=user)

    # Should not raise exception
    auth_verify_token(token=tokens["access"])

    with pytest.raises(InvalidTokenError):
        auth_verify_token(token="invalid-token")
