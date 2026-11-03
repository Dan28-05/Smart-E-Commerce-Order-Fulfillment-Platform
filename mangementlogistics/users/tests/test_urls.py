from __future__ import annotations

from django.urls import resolve, reverse


def test_user_list_url():
    """Test resolution of user list URL."""
    assert reverse("users:user-list") == "/users/"
    assert resolve("/users/").view_name == "users:user-list"


def test_user_login_url():
    """Test resolution of login URL."""
    assert reverse("users:login") == "/users/login/"
    assert resolve("/users/login/").view_name == "users:login"


def test_user_logout_url():
    """Test resolution of logout URL."""
    assert reverse("users:logout") == "/users/logout/"
    assert resolve("/users/logout/").view_name == "users:logout"


def test_user_create_url():
    """Test resolution of user create URL."""
    assert reverse("users:user-create") == "/users/create/"
    assert resolve("/users/create/").view_name == "users:user-create"


def test_password_change_url():
    """Test resolution of password change URL."""
    assert reverse("users:password-change") == "/users/password/change/"
    assert resolve("/users/password/change/").view_name == "users:password-change"
