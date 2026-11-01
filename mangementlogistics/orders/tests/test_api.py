# mangementlogistics/orders/tests/test_api.py
from decimal import Decimal

from django.urls import reverse
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from mangementlogistics.orders.constants import OrderStatus
from mangementlogistics.orders.services import order_create
from mangementlogistics.users.constants import UserRole
from mangementlogistics.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def customer_user():
    return User.objects.create_user(
        username="api_cust@example.com",
        email="api_cust@example.com",
        password="CustomerPassword123!",
        name="Customer API",
        role=UserRole.CUSTOMER,
    )


@pytest.fixture
def driver_user():
    return User.objects.create_user(
        username="api_driver@example.com",
        email="api_driver@example.com",
        password="DriverPassword123!",
        name="Driver API",
        role=UserRole.DRIVER,
    )


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        username="api_admin@example.com",
        email="api_admin@example.com",
        password="AdminPassword123!",
        name="Admin API",
        role=UserRole.ADMIN,
    )


def test_order_create_api(api_client, customer_user):
    api_client.force_authenticate(user=customer_user)
    url = reverse("orders_api:order-list-create")

    payload = {
        "sender_name": "Nguyen Van A",
        "sender_phone": "0911111111",
        "sender_address": "Ha Noi",
        "receiver_name": "Tran Van B",
        "receiver_phone": "0922222222",
        "receiver_address": "Ho Chi Minh",
        "weight": "1.50",
        "item_description": "Documents",
        "cod_amount": "250000.00",
        "shipping_fee": "35000.00",
    }

    response = api_client.post(url, data=payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert "tracking_number" in response.data
    assert response.data["status"] == OrderStatus.PENDING
    assert response.data["customer"]["email"] == customer_user.email


def test_order_list_api_filter_by_role(api_client, customer_user, driver_user):
    # Order 1 for customer
    o1 = order_create(
        customer=customer_user,
        sender_name="Sender 1",
        sender_phone="0901",
        sender_address="Addr 1",
        receiver_name="Receiver 1",
        receiver_phone="0902",
        receiver_address="Addr 2",
    )

    other_customer = User.objects.create_user(
        username="other_cust@example.com",
        email="other_cust@example.com",
        password="ValidPassword123!",
        role=UserRole.CUSTOMER,
    )

    # Order 2 for other customer
    order_create(
        customer=other_customer,
        sender_name="Sender 2",
        sender_phone="0903",
        sender_address="Addr 3",
        receiver_name="Receiver 2",
        receiver_phone="0904",
        receiver_address="Addr 4",
    )

    # Customer only sees their 1 order
    api_client.force_authenticate(user=customer_user)
    url = reverse("orders_api:order-list-create")
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["id"] == o1.id


def test_order_status_update_api(api_client, customer_user, admin_user, driver_user):
    order = order_create(
        customer=customer_user,
        sender_name="Sender",
        sender_phone="0901",
        sender_address="Addr 1",
        receiver_name="Receiver",
        receiver_phone="0902",
        receiver_address="Addr 2",
    )

    api_client.force_authenticate(user=admin_user)
    status_url = reverse("orders_api:order-status-update", kwargs={"order_id": order.id})

    # Admin confirms & assigns driver
    resp = api_client.post(
        status_url,
        data={"status": OrderStatus.CONFIRMED, "driver_id": driver_user.id},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["status"] == OrderStatus.CONFIRMED
    assert resp.data["driver"]["id"] == driver_user.id


def test_order_cancel_api(api_client, customer_user):
    order = order_create(
        customer=customer_user,
        sender_name="Sender",
        sender_phone="0901",
        sender_address="Addr 1",
        receiver_name="Receiver",
        receiver_phone="0902",
        receiver_address="Addr 2",
    )

    api_client.force_authenticate(user=customer_user)
    cancel_url = reverse("orders_api:order-cancel", kwargs={"order_id": order.id})

    resp = api_client.post(cancel_url, data={"reason": "Wrong address"}, format="json")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["status"] == OrderStatus.CANCELLED


def test_order_public_tracking_api(api_client, customer_user):
    order = order_create(
        customer=customer_user,
        sender_name="Sender Track",
        sender_phone="0901",
        sender_address="Addr 1",
        receiver_name="Receiver Track",
        receiver_phone="0902",
        receiver_address="Addr 2",
    )

    # Unauthenticated public request
    api_client.credentials()
    track_url = reverse("orders_api:order-track", kwargs={"tracking_number": order.tracking_number})
    resp = api_client.get(track_url)

    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["tracking_number"] == order.tracking_number
    assert resp.data["receiver_name"] == "Receiver Track"
