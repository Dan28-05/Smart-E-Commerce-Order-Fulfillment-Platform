from __future__ import annotations

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
def user():
    return User.objects.create_user(
        username="api_user@example.com",
        email="api_user@example.com",
        password="ValidPassword123!",
        name="API User",
        role=UserRole.CUSTOMER,
    )


def test_user_list_api(api_client, user):
    """Test retrieving user list from API."""
    api_client.force_authenticate(user=user)
    response = api_client.get("/api/users/")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) >= 1
    assert any(u["email"] == user.email for u in response.data)


def test_user_me_api(api_client, user):
    """Test retrieving authenticated user profile."""
    api_client.force_authenticate(user=user)
    response = api_client.get("/api/users/me/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["email"] == user.email
    assert response.data["name"] == user.name
