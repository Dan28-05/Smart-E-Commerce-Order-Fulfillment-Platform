from http import HTTPStatus

from django.urls import reverse
import pytest

from mangementlogistics.users.constants import UserRole
from mangementlogistics.users.models import User

pytestmark = pytest.mark.django_db


class TestUserAdmin:
    """Tests for User admin site views and actions."""

    def test_changelist(self, admin_client):
        url = reverse("admin:users_user_changelist")
        response = admin_client.get(url)
        assert response.status_code == HTTPStatus.OK

    def test_search(self, admin_client):
        url = reverse("admin:users_user_changelist")
        response = admin_client.get(url, data={"q": "test"})
        assert response.status_code == HTTPStatus.OK

    def test_view_user(self, admin_client):
        user = User.objects.create_user(
            username="admin_view_test@example.com",
            email="admin_view_test@example.com",
            password="SamplePassword123!",
            name="Admin View Test",
            role=UserRole.ADMIN,
        )
        url = reverse("admin:users_user_change", kwargs={"object_id": user.pk})
        response = admin_client.get(url)
        assert response.status_code == HTTPStatus.OK
