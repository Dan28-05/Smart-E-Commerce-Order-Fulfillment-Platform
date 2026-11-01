# mangementlogistics/orders/tests/test_services.py
from decimal import Decimal

import pytest

from mangementlogistics.orders.constants import (
    OrderPaymentMethod,
    OrderPaymentStatus,
    OrderStatus,
)
from mangementlogistics.orders.exceptions import (
    DriverAssignmentError,
    InvalidOrderStatusError,
    OrderPermissionDeniedError,
)
from mangementlogistics.orders.services import (
    order_cancel,
    order_create,
    order_delete,
    order_update,
    order_update_status,
)
from mangementlogistics.users.constants import UserRole
from mangementlogistics.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def customer_user():
    return User.objects.create_user(
        username="cust@example.com",
        email="cust@example.com",
        password="CustomerPassword123!",
        name="Customer Test",
        role=UserRole.CUSTOMER,
    )


@pytest.fixture
def driver_user():
    return User.objects.create_user(
        username="driv@example.com",
        email="driv@example.com",
        password="DriverPassword123!",
        name="Driver Test",
        role=UserRole.DRIVER,
    )


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        username="admin_test@example.com",
        email="admin_test@example.com",
        password="AdminPassword123!",
        name="Admin Test",
        role=UserRole.ADMIN,
    )


def test_order_create_success(customer_user):
    order = order_create(
        customer=customer_user,
        sender_name="Sender Name",
        sender_phone="0901111111",
        sender_address="123 Nguyen Hue, Q1, HCM",
        receiver_name="Receiver Name",
        receiver_phone="0902222222",
        receiver_address="456 Le Loi, Q1, HCM",
        weight=Decimal("2.5"),
        item_description="Electronics",
        cod_amount=Decimal("500000"),
        shipping_fee=Decimal("30000"),
    )

    assert order.id is not None
    assert order.tracking_number.startswith("ORD-")
    assert order.customer == customer_user
    assert order.status == OrderStatus.PENDING
    assert order.total_amount == Decimal("530000")


def test_order_create_invalid_driver(customer_user):
    fake_driver = User.objects.create_user(
        username="fake_driver@example.com",
        email="fake_driver@example.com",
        password="ValidPassword123!",
        role=UserRole.CUSTOMER,
    )

    with pytest.raises(DriverAssignmentError):
        order_create(
            customer=customer_user,
            driver=fake_driver,
            sender_name="Sender",
            sender_phone="0901",
            sender_address="Addr 1",
            receiver_name="Receiver",
            receiver_phone="0902",
            receiver_address="Addr 2",
        )


def test_order_update_by_customer_and_permission_denied(customer_user, admin_user):
    order = order_create(
        customer=customer_user,
        sender_name="Sender Old",
        sender_phone="0901",
        sender_address="Addr 1",
        receiver_name="Receiver Old",
        receiver_phone="0902",
        receiver_address="Addr 2",
    )

    other_user = User.objects.create_user(
        username="stranger@example.com",
        email="stranger@example.com",
        password="ValidPassword123!",
        role=UserRole.CUSTOMER,
    )

    # Stranger cannot update
    with pytest.raises(OrderPermissionDeniedError):
        order_update(order=order, actor=other_user, receiver_name="Hacked Name")

    # Owner can update
    updated_order = order_update(order=order, actor=customer_user, receiver_name="Receiver New")
    assert updated_order.receiver_name == "Receiver New"


def test_order_update_status_lifecycle(customer_user, driver_user, admin_user):
    order = order_create(
        customer=customer_user,
        sender_name="Sender",
        sender_phone="0901",
        sender_address="Addr 1",
        receiver_name="Receiver",
        receiver_phone="0902",
        receiver_address="Addr 2",
        cod_amount=Decimal("100000"),
    )

    # 1. Admin confirms and assigns driver
    order_update_status(
        order=order,
        new_status=OrderStatus.CONFIRMED,
        actor=admin_user,
        driver_id=driver_user.id,
    )
    assert order.status == OrderStatus.CONFIRMED
    assert order.driver == driver_user

    # 2. Driver picks up
    order_update_status(
        order=order,
        new_status=OrderStatus.PICKED_UP,
        actor=driver_user,
    )
    assert order.status == OrderStatus.PICKED_UP

    # 3. Driver in transit
    order_update_status(
        order=order,
        new_status=OrderStatus.IN_TRANSIT,
        actor=driver_user,
    )
    assert order.status == OrderStatus.IN_TRANSIT

    # 4. Driver delivers
    order_update_status(
        order=order,
        new_status=OrderStatus.DELIVERED,
        actor=driver_user,
    )
    assert order.status == OrderStatus.DELIVERED
    assert order.delivered_at is not None
    assert order.payment_status == OrderPaymentStatus.PAID

    # 5. Cannot modify finished order
    with pytest.raises(InvalidOrderStatusError):
        order_update_status(
            order=order,
            new_status=OrderStatus.IN_TRANSIT,
            actor=admin_user,
        )


def test_order_cancel(customer_user, admin_user):
    order = order_create(
        customer=customer_user,
        sender_name="Sender",
        sender_phone="0901",
        sender_address="Addr 1",
        receiver_name="Receiver",
        receiver_phone="0902",
        receiver_address="Addr 2",
    )

    cancelled = order_cancel(order=order, actor=customer_user, reason="Customer changed mind")
    assert cancelled.status == OrderStatus.CANCELLED
    assert "Customer changed mind" in cancelled.notes


def test_order_delete(customer_user, admin_user):
    order = order_create(
        customer=customer_user,
        sender_name="Sender",
        sender_phone="0901",
        sender_address="Addr 1",
        receiver_name="Receiver",
        receiver_phone="0902",
        receiver_address="Addr 2",
    )

    order_delete(order=order, actor=customer_user)
    assert not User.objects.filter(id=order.id).exists()
