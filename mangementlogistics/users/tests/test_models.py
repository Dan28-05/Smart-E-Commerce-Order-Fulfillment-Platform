from __future__ import annotations

import pytest

from mangementlogistics.users.constants import UserRole
from mangementlogistics.users.models import User

pytestmark = pytest.mark.django_db


def test_user_creation_and_str():
    """
    Test user model creation, fields, and string representation.
    """
    user = User.objects.create_user(
        username="model_test@example.com",
        email="model_test@example.com",
        password="ValidPassword123!",
        name="Test Model User",
        role=UserRole.DRIVER,
    )
    assert user.name == "Test Model User"
    assert user.role == UserRole.DRIVER
    assert str(user) == "model_test@example.com (Driver)"
