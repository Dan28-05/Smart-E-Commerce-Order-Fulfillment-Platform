from __future__ import annotations

import pytest

from mangementlogistics.users.constants import UserRole
from mangementlogistics.users.forms import UserCreateForm, UserLoginForm
from mangementlogistics.users.models import User

pytestmark = pytest.mark.django_db


def test_user_create_form_valid():
    """
    Test UserCreateForm validation with valid input data.
    """
    form_data = {
        "name": "Form User",
        "email": "form_user@example.com",
        "password": "ValidPassword123!",
        "password_confirm": "ValidPassword123!",
        "role": UserRole.CUSTOMER,
        "phone_number": "0911222333",
        "address": "123 Hanoi Street",
    }
    form = UserCreateForm(data=form_data)
    assert form.is_valid(), form.errors
    user = form.save()
    assert user.email == "form_user@example.com"
    assert user.role == UserRole.CUSTOMER


def test_user_create_form_password_mismatch():
    """
    Test UserCreateForm fails when password and confirmation do not match.
    """
    form_data = {
        "name": "Form User",
        "email": "mismatch@example.com",
        "password": "ValidPassword123!",
        "password_confirm": "DifferentPassword123!",
        "role": UserRole.CUSTOMER,
    }
    form = UserCreateForm(data=form_data)
    assert not form.is_valid()
    assert "password_confirm" in form.errors


def test_user_login_form_valid():
    """
    Test UserLoginForm validation with valid credentials structure.
    """
    form = UserLoginForm(
        data={
            "email": "login@example.com",
            "password": "SamplePassword123!",
            "remember_me": True,
        }
    )
    assert form.is_valid(), form.errors
