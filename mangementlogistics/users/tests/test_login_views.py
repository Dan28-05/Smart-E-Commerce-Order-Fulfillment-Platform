# mangementlogistics/users/tests/test_login_views.py
from django.test import Client
from django.urls import reverse
import pytest

from mangementlogistics.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def user():
    return User.objects.create_user(
        username="login_test@example.com",
        email="login_test@example.com",
        password="ValidPassword123!",
        name="Login Tester",
    )


def test_user_login_view_get(client):
    response = client.get(reverse("users:login"))
    assert response.status_code == 200
    assert "Đăng nhập" in response.content.decode("utf-8")


def test_user_login_view_post_success(client, user):
    response = client.post(
        reverse("users:login"),
        data={"email": "login_test@example.com", "password": "ValidPassword123!"},
        follow=True,
    )
    assert response.status_code == 200
    assert response.context["user"].is_authenticated
    assert response.context["user"].email == "login_test@example.com"


def test_user_login_view_post_invalid_credentials(client, user):
    response = client.post(
        reverse("users:login"),
        data={"email": "login_test@example.com", "password": "WrongPassword!"},
    )
    assert response.status_code == 200
    assert "Email hoặc mật khẩu không chính xác" in response.content.decode("utf-8")


def test_user_logout_view(client, user):
    client.force_login(user)
    response = client.get(reverse("users:logout"), follow=True)
    assert response.status_code == 200
    assert not response.context["user"].is_authenticated

