# mangementlogistics/authentication/tests/test_api.py
import pytest
from django.urls import reverse
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
