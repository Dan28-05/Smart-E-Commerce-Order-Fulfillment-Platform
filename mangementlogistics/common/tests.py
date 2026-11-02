# mangementlogistics/common/tests.py
from django.test import Client
from django.urls import reverse
import pytest

from mangementlogistics.orders.constants import OrderPaymentMethod, OrderPaymentStatus, OrderStatus
from mangementlogistics.orders.models import Order
from mangementlogistics.users.constants import UserRole
from mangementlogistics.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def user():
    return User.objects.create_user(
        username="home_user@example.com",
        email="home_user@example.com",
        password="ValidPassword123!",
        name="Nguyễn Văn A",
        role=UserRole.CUSTOMER,
    )


def test_home_view_guest(client):
    """
    Ensure unauthenticated visitors see the public landing page with quick tracking and CTAs.
    """
    response = client.get(reverse("home"))
    assert response.status_code == 200
    assert response.context["is_dashboard"] is False
    content = response.content.decode("utf-8")
    assert "Giải Pháp Quản Lý Logistics" in content
    assert "Tra cứu ngay" in content
    assert "Đăng ký tài khoản" in content
    assert "Tra cứu bưu kiện" in content


def test_home_view_authenticated_dashboard(client, user):
    """
    Ensure authenticated users see the operational dashboard with calculated KPI statistics and recent orders.
    """
    # Create sample orders
    Order.objects.create(
        customer=user,
        sender_name="Sender",
        sender_phone="0911111111",
        sender_address="Hanoi",
        receiver_name="Receiver 1",
        receiver_phone="0922222222",
        receiver_address="HCM",
        weight=1.5,
        cod_amount=250000,
        shipping_fee=30000,
        payment_method=OrderPaymentMethod.COD,
        payment_status=OrderPaymentStatus.UNPAID,
        status=OrderStatus.PENDING,
    )
    Order.objects.create(
        customer=user,
        sender_name="Sender",
        sender_phone="0911111111",
        sender_address="Hanoi",
        receiver_name="Receiver 2",
        receiver_phone="0933333333",
        receiver_address="Danang",
        weight=2.0,
        cod_amount=500000,
        shipping_fee=40000,
        payment_method=OrderPaymentMethod.COD,
        payment_status=OrderPaymentStatus.PAID,
        status=OrderStatus.DELIVERED,
    )
    Order.objects.create(
        customer=user,
        sender_name="Sender",
        sender_phone="0911111111",
        sender_address="Hanoi",
        receiver_name="Receiver 3",
        receiver_phone="0944444444",
        receiver_address="Hue",
        weight=0.5,
        cod_amount=150000,
        shipping_fee=25000,
        payment_method=OrderPaymentMethod.COD,
        payment_status=OrderPaymentStatus.UNPAID,
        status=OrderStatus.IN_TRANSIT,
    )

    client.force_login(user)
    response = client.get(reverse("home"))

    assert response.status_code == 200
    assert response.context["is_dashboard"] is True
    assert response.context["total_orders"] == 3
    assert response.context["pending_orders"] == 1
    assert response.context["delivering_orders"] == 1
    assert response.context["delivered_orders"] == 1
    assert response.context["total_cod"] == 500000

    content = response.content.decode("utf-8")
    assert "Xin chào, Nguyễn Văn A" in content
    assert "Đơn hàng gần đây" in content
    assert "Receiver 1" in content
    assert "Receiver 2" in content
