# mangementlogistics/users/tests/test_password_views.py
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import Client
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
import pytest

from mangementlogistics.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def user():
    return User.objects.create_user(
        username="web_user@example.com",
        email="web_user@example.com",
        password="InitialPassword123!",
        name="Web User",
    )


def test_password_change_view_authenticated(client, user):
    client.force_login(user)
    url = reverse("users:password-change")

    # GET
    response = client.get(url)
    assert response.status_code == 200
    assert "Đổi mật khẩu" in response.content.decode("utf-8")

    # POST Valid Change
    post_resp = client.post(
        url,
        data={
            "old_password": "InitialPassword123!",
            "new_password": "NewWebPassword123!",
            "new_password_confirm": "NewWebPassword123!",
        },
        follow=True,
    )
    assert post_resp.status_code == 200
    user.refresh_from_db()
    assert user.check_password("NewWebPassword123!")


def test_password_change_view_unauthenticated(client):
    url = reverse("users:password-change")
    response = client.get(url, follow=True)
    # Redirects to home
    assert response.status_code == 200


def test_password_reset_web_flow(client, user):
    mail.outbox = []

    # 1. Request reset
    req_url = reverse("users:password-reset-request")
    get_req = client.get(req_url)
    assert get_req.status_code == 200

    post_req = client.post(req_url, data={"email": user.email}, follow=True)
    assert post_req.status_code == 200
    assert len(mail.outbox) == 1

    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    # 2. Open confirm page
    conf_url = reverse("users:password-reset-confirm", kwargs={"uidb64": uidb64, "token": token})
    get_conf = client.get(conf_url)
    assert get_conf.status_code == 200
    assert "Tạo mật khẩu mới" in get_conf.content.decode("utf-8")

    # 3. Post new password
    post_conf = client.post(
        conf_url,
        data={
            "new_password": "ResetFromWeb123!",
            "new_password_confirm": "ResetFromWeb123!",
        },
        follow=True,
    )
    assert post_conf.status_code == 200
    user.refresh_from_db()
    assert user.check_password("ResetFromWeb123!")

