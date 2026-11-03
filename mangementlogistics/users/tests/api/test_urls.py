from __future__ import annotations

from django.urls import resolve, reverse


def test_user_list_create_url():
    """Test resolution of user list/create API endpoint."""
    assert reverse("users_api:user-list-create") == "/api/users/"
    assert resolve("/api/users/").view_name == "users_api:user-list-create"


def test_user_me_url():
    """Test resolution of user me profile API endpoint."""
    assert reverse("users_api:user-me") == "/api/users/me/"
    assert resolve("/api/users/me/").view_name == "users_api:user-me"


def test_user_detail_url():
    """Test resolution of user detail API endpoint."""
    assert reverse("users_api:user-detail", kwargs={"user_id": 1}) == "/api/users/1/"
    assert resolve("/api/users/1/").view_name == "users_api:user-detail"
