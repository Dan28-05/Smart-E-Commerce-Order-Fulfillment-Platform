from __future__ import annotations

from django.test import Client
from django.urls import reverse
import pytest

from mangementlogistics.users.constants import UserRole
from mangementlogistics.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def user():
    return User.objects.create_user(
        username="view_tester@example.com",
        email="view_tester@example.com",
        password="ValidPassword123!",
        name="View Tester",
        role=UserRole.CUSTOMER,
    )


def test_user_list_view(client, user):
    """
    Test user list view renders with HTTP 200 and displays user list.
    """
    url = reverse("users:user-list")
    response = client.get(url)
    assert response.status_code == 200
    assert "view_tester@example.com" in response.content.decode("utf-8")


def test_user_create_view_get(client):
    """
    Test user creation view GET request returns form.
    """
    url = reverse("users:user-create")
    response = client.get(url)
    assert response.status_code == 200
    assert "Thêm người dùng mới" in response.content.decode("utf-8")


def test_user_create_view_post_success(client):
    """
    Test user creation view POST request creates user and redirects.
    """
    url = reverse("users:user-create")
    payload = {
        "name": "New Web User",
        "email": "new_web_user@example.com",
        "password": "ValidPassword123!",
        "password_confirm": "ValidPassword123!",
        "role": UserRole.CUSTOMER,
    }
    response = client.post(url, data=payload, follow=True)
    assert response.status_code == 200
    assert User.objects.filter(email="new_web_user@example.com").exists()


def test_user_profile_view_unauthenticated(client):
    """
    Test unauthenticated access to profile view redirects to login page.
    """
    url = reverse("users:profile")
    response = client.get(url)
    assert response.status_code == 302
    assert "/users/login/" in response.url


def test_user_profile_view_authenticated_get_and_post(client, user):
    """
    Test authenticated user can view and update profile information.
    """
    client.force_login(user)
    url = reverse("users:profile")

    # GET
    response = client.get(url)
    assert response.status_code == 200
    assert user.email in response.content.decode("utf-8")
    assert "Cập nhật thông tin cá nhân" in response.content.decode("utf-8")

    # POST update
    payload = {
        "name": "Updated Name",
        "phone_number": "0988776655",
        "address": "999 Logistics Boulevard",
    }
    post_resp = client.post(url, data=payload, follow=True)
    assert post_resp.status_code == 200
    user.refresh_from_db()
    assert user.name == "Updated Name"
    assert user.phone_number == "0988776655"
    assert user.address == "999 Logistics Boulevard"

