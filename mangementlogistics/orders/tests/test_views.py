# mangementlogistics/orders/tests/test_views.py
from decimal import Decimal

from django.test import Client
from django.urls import reverse
import pytest

from mangementlogistics.orders.constants import OrderStatus
from mangementlogistics.orders.services import order_create
from mangementlogistics.users.constants import UserRole
from mangementlogistics.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def customer_user():
    return User.objects.create_user(
        username="web_order_cust@example.com",
        email="web_order_cust@example.com",
        password="CustomerPassword123!",
        name="Web Customer",
        role=UserRole.CUSTOMER,
    )


def test_order_web_crud_lifecycle(client, customer_user):
    client.force_login(customer_user)

    # 1. GET Create Form
    create_url = reverse("orders:order-create")
    resp_get = client.get(create_url)
    assert resp_get.status_code == 200
    assert "Tạo đơn hàng mới" in resp_get.content.decode("utf-8")

    # 2. POST Create
    create_payload = {
        "sender_name": "Web Sender",
        "sender_phone": "0912345678",
        "sender_address": "123 Tran Hung Dao",
        "receiver_name": "Web Receiver",
        "receiver_phone": "0987654321",
        "receiver_address": "456 Le Loi",
        "weight": "2.0",
        "item_description": "Clothes",
        "notes": "Deliver in morning",
        "cod_amount": "150000",
        "shipping_fee": "25000",
        "payment_method": "COD",
    }
    resp_create = client.post(create_url, data=create_payload, follow=True)
    assert resp_create.status_code == 200

    # 3. GET List
    list_url = reverse("orders:order-list")
    resp_list = client.get(list_url)
    assert resp_list.status_code == 200
    assert "Web Receiver" in resp_list.content.decode("utf-8")

    # 4. GET Detail
    order = customer_user.orders.first()
    assert order is not None
    detail_url = reverse("orders:order-detail", kwargs={"order_id": order.id})
    resp_detail = client.get(detail_url)
    assert resp_detail.status_code == 200
    assert order.tracking_number in resp_detail.content.decode("utf-8")

    # 5. GET & POST Update
    edit_url = reverse("orders:order-update", kwargs={"order_id": order.id})
    edit_payload = create_payload.copy()
    edit_payload["receiver_name"] = "Web Receiver Updated"
    resp_edit = client.post(edit_url, data=edit_payload, follow=True)
    assert resp_edit.status_code == 200
    order.refresh_from_db()
    assert order.receiver_name == "Web Receiver Updated"

    # 6. POST Cancel
    cancel_url = reverse("orders:order-cancel", kwargs={"order_id": order.id})
    resp_cancel = client.post(cancel_url, data={"reason": "Cancel request"}, follow=True)
    assert resp_cancel.status_code == 200
    order.refresh_from_db()
    assert order.status == OrderStatus.CANCELLED

    # 7. Public Tracking
    track_url = reverse("orders:order-track")
    resp_track = client.get(track_url, data={"tracking": order.tracking_number})
    assert resp_track.status_code == 200
    assert "Web Receiver Updated" in resp_track.content.decode("utf-8")

