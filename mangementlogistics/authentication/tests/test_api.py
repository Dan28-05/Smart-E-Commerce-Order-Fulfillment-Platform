# mangementlogistics/authentication/tests/test_api.py
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from mangementlogistics.users.constants import UserRole
from mangementlogistics.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def created_user():
    return User.objects.create_user(
        username="driver1@example.com",
        email="driver1@example.com",
        password="ValidPassword123!",
        name="Driver One",
        role=UserRole.DRIVER,
        phone_number="0901234567",
        address="123 Tran Hung Dao",
    )


def test_login_api_success(api_client, created_user):
    url = reverse("auth_api:login")
    response = api_client.post(
        url,
        data={
            "email": "driver1@example.com",
            "password": "ValidPassword123!",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" in response.data
    assert "user" in response.data
    assert response.data["user"]["email"] == "driver1@example.com"
    assert response.data["user"]["role"] == UserRole.DRIVER


def test_login_api_wrong_password(api_client, created_user):
    url = reverse("auth_api:login")
    response = api_client.post(
        url,
        data={
            "email": "driver1@example.com",
            "password": "WrongPassword!",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "error" in response.data


def test_login_api_inactive_user(api_client, created_user):
    created_user.is_active = False
    created_user.save()

    url = reverse("auth_api:login")
    response = api_client.post(
        url,
        data={
            "email": "driver1@example.com",
            "password": "ValidPassword123!",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "error" in response.data


def test_token_refresh_api(api_client, created_user):
    login_url = reverse("auth_api:login")
    login_resp = api_client.post(
        login_url,
        data={"email": created_user.email, "password": "ValidPassword123!"},
        format="json",
    )
    refresh_token = login_resp.data["refresh"]

    refresh_url = reverse("auth_api:token-refresh")
    refresh_resp = api_client.post(
        refresh_url,
        data={"refresh": refresh_token},
        format="json",
    )

    assert refresh_resp.status_code == status.HTTP_200_OK
    assert "access" in refresh_resp.data


def test_token_verify_api(api_client, created_user):
    login_url = reverse("auth_api:login")
    login_resp = api_client.post(
        login_url,
        data={"email": created_user.email, "password": "ValidPassword123!"},
        format="json",
    )
    access_token = login_resp.data["access"]

    verify_url = reverse("auth_api:token-verify")
    verify_resp = api_client.post(
        verify_url,
        data={"token": access_token},
        format="json",
    )

    assert verify_resp.status_code == status.HTTP_200_OK
    assert verify_resp.data["valid"] is True


def test_jwt_access_protected_me_endpoint(api_client, created_user):
    # Without token -> 401
    me_url = reverse("users_api:user-me")
    unauth_resp = api_client.get(me_url)
    assert unauth_resp.status_code == status.HTTP_401_UNAUTHORIZED

    # Obtain token
    login_url = reverse("auth_api:login")
    login_resp = api_client.post(
        login_url,
        data={"email": created_user.email, "password": "ValidPassword123!"},
        format="json",
    )
    access_token = login_resp.data["access"]

    # With Bearer token -> 200 OK
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    auth_resp = api_client.get(me_url)
    assert auth_resp.status_code == status.HTTP_200_OK
    assert auth_resp.data["email"] == created_user.email
    assert auth_resp.data["role"] == created_user.role


def test_change_password_api(api_client, created_user):
    # Login first
    login_url = reverse("auth_api:login")
    login_resp = api_client.post(
        login_url,
        data={"email": created_user.email, "password": "ValidPassword123!"},
        format="json",
    )
    access_token = login_resp.data["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    url = reverse("auth_api:change-password")

    # Mismatch passwords -> 400
    bad_resp = api_client.post(
        url,
        data={
            "old_password": "ValidPassword123!",
            "new_password": "BrandNewPassword123!",
            "new_password_confirm": "MismatchPassword123!",
        },
        format="json",
    )
    assert bad_resp.status_code == status.HTTP_400_BAD_REQUEST

    # Weak new password -> 400
    weak_resp = api_client.post(
        url,
        data={
            "old_password": "ValidPassword123!",
            "new_password": "weak",
            "new_password_confirm": "weak",
        },
        format="json",
    )
    assert weak_resp.status_code == status.HTTP_400_BAD_REQUEST

    # Valid change -> 200 OK
    good_resp = api_client.post(
        url,
        data={
            "old_password": "ValidPassword123!",
            "new_password": "BrandNewPassword123!",
            "new_password_confirm": "BrandNewPassword123!",
        },
        format="json",
    )
    assert good_resp.status_code == status.HTTP_200_OK


def test_password_reset_flow_via_api(api_client, created_user):
    mail.outbox = []

    # 1. Request password reset
    req_url = reverse("auth_api:password-reset-request")
    req_resp = api_client.post(req_url, data={"email": created_user.email}, format="json")
    assert req_resp.status_code == status.HTTP_200_OK
    assert len(mail.outbox) == 1

    uidb64 = urlsafe_base64_encode(force_bytes(created_user.pk))
    token = default_token_generator.make_token(created_user)

    # 2. Validate token
    val_url = reverse("auth_api:password-reset-validate-token")
    val_resp = api_client.post(val_url, data={"uidb64": uidb64, "token": token}, format="json")
    assert val_resp.status_code == status.HTTP_200_OK
    assert val_resp.data["valid"] is True

    # 3. Confirm password reset
    conf_url = reverse("auth_api:password-reset-confirm")
    conf_resp = api_client.post(
        conf_url,
        data={
            "uidb64": uidb64,
            "token": token,
            "new_password": "ResetPassword123!",
            "new_password_confirm": "ResetPassword123!",
        },
        format="json",
    )
    assert conf_resp.status_code == status.HTTP_200_OK

    # 4. Login with newly reset password
    login_url = reverse("auth_api:login")
    new_login = api_client.post(
        login_url,
        data={"email": created_user.email, "password": "ResetPassword123!"},
        format="json",
    )
    assert new_login.status_code == status.HTTP_200_OK
