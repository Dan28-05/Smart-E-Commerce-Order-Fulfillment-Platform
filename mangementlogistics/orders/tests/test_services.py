# mangementlogistics/orders/tests/test_services.py
from decimal import Decimal

import pytest

from mangementlogistics.orders.constants import (
    CODReconciliationStatus,
    OrderPaymentMethod,
    OrderPaymentStatus,
    OrderStatus,
)
from mangementlogistics.orders.exceptions import (
    CODReconciliationError,
    DriverAssignmentError,
    InvalidOrderStatusError,
    OrderPermissionDeniedError,
)
from mangementlogistics.orders.models import CODReconciliation, Order
from mangementlogistics.orders.selectors import (
    cod_reconciliation_get_summary_stats,
    cod_reconciliation_list,
)
from mangementlogistics.orders.services import (
    calculate_shipping_rates,
    cod_reconciliation_confirm,
    cod_reconciliation_generate,
    cod_reconciliation_mark_paid,
    order_add_checkpoint,
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


def test_order_tracking_history_lifecycle(customer_user, driver_user, admin_user):
    order = order_create(
        customer=customer_user,
        sender_name="Sender",
        sender_phone="0901",
        sender_address="Kho Long Bien",
        receiver_name="Receiver",
        receiver_phone="0902",
        receiver_address="Quan 1 HCM",
    )
    # Check initial event
    events = order.tracking_history.all()
    assert events.count() == 1
    assert events[0].status == OrderStatus.PENDING
    assert "khởi tạo thành công" in events[0].note

    # Update status to CONFIRMED
    order_update_status(
        order=order,
        new_status=OrderStatus.CONFIRMED,
        actor=admin_user,
        driver_id=driver_user.id,
        location="Hub Phan Loai",
        note="Đã xác nhận đơn hàng",
    )
    assert order.tracking_history.count() == 2
    latest = order.tracking_history.first()
    assert latest.status == OrderStatus.CONFIRMED
    assert latest.location == "Hub Phan Loai"

    # Add custom checkpoint
    checkpoint = order_add_checkpoint(
        order=order,
        location="Tram Trung Chuyen Da Nang",
        note="Kien hang dang tren xe container trung chuyen",
        actor=driver_user,
    )
    assert checkpoint.location == "Tram Trung Chuyen Da Nang"
    assert order.tracking_history.count() == 3


def test_calculate_shipping_rates_intra_province():
    """
    Test shipping calculation within the same province (intra-province route).
    """
    res = calculate_shipping_rates(
        sender_province="Hà Nội",
        receiver_province="Hà Nội",
        weight=1.5,
    )
    assert res["route_type"] == "INTRA_PROVINCE"
    assert res["route_label"] == "Nội tỉnh"
    assert res["chargeable_weight"] == 1.5
    assert not res["is_volumetric"]
    assert len(res["plans"]) == 3

    # Base cost for intra-province up to 2kg is 18,000 VND
    standard_plan = next(p for p in res["plans"] if p["code"] == "STANDARD")
    assert standard_plan["shipping_fee"] == 18000
    assert standard_plan["total_fee"] == 18000


def test_calculate_shipping_rates_intra_region():
    """
    Test shipping calculation within the same region (intra-region route).
    """
    res = calculate_shipping_rates(
        sender_province="Hà Nội",
        receiver_province="Hải Phòng",
        weight=1.0,
    )
    assert res["route_type"] == "INTRA_REGION"
    assert "Nội miền" in res["route_label"]
    standard_plan = next(p for p in res["plans"] if p["code"] == "STANDARD")
    assert standard_plan["shipping_fee"] == 30000


def test_calculate_shipping_rates_inter_region():
    """
    Test shipping calculation across different regions (inter-region route).
    """
    res = calculate_shipping_rates(
        sender_province="Hà Nội",
        receiver_province="TP. Hồ Chí Minh",
        weight=0.5,
    )
    assert res["route_type"] == "INTER_REGION"
    assert "Liên miền" in res["route_label"]
    standard_plan = next(p for p in res["plans"] if p["code"] == "STANDARD")
    assert standard_plan["shipping_fee"] == 45000


def test_calculate_shipping_rates_volumetric_weight():
    """
    Test volumetric weight calculation: (L x W x H) / 5000 overrides light actual weight.
    """
    # 50cm x 40cm x 30cm = 60,000 / 5,000 = 12.0 kg > 1.0 kg actual weight
    res = calculate_shipping_rates(
        sender_province="Hà Nội",
        receiver_province="Hà Nội",
        weight=1.0,
        length=50,
        width=40,
        height=30,
    )
    assert res["is_volumetric"] is True
    assert res["actual_weight"] == 1.0
    assert res["volumetric_weight"] == 12.0
    assert res["chargeable_weight"] == 12.0


def test_calculate_shipping_rates_insurance_cod():
    """
    Test insurance surcharge when COD / declared value exceeds 3,000,000 VND.
    """
    # 5,000,000 VND -> excess 2,000,000 * 0.005 = 10,000 VND insurance fee
    res = calculate_shipping_rates(
        sender_province="Hà Nội",
        receiver_province="Hà Nội",
        weight=1.0,
        cod_amount=5000000,
    )
    assert res["insurance_fee"] == 10000
    standard_plan = next(p for p in res["plans"] if p["code"] == "STANDARD")
    assert standard_plan["insurance_fee"] == 10000
    assert standard_plan["total_fee"] == standard_plan["shipping_fee"] + 10000


def test_cod_reconciliation_model_defaults(customer_user):
    """
    Test CODReconciliation model creation, generated code, and initial status.
    """
    rec = CODReconciliation.objects.create(
        customer=customer_user,
        total_orders_count=3,
        total_cod_amount=Decimal("1500000.00"),
        total_shipping_fees=Decimal("90000.00"),
        net_payout_amount=Decimal("1410000.00"),
    )
    assert rec.code.startswith("REC-")
    assert rec.status == CODReconciliationStatus.PENDING
    assert rec.total_orders_count == 3
    assert rec.net_payout_amount == Decimal("1410000.00")
    assert str(rec).startswith(rec.code)


def test_cod_reconciliation_generate_no_orders_raises_error(customer_user):
    """
    Ensure attempting to generate reconciliation with no delivered COD orders raises error.
    """
    with pytest.raises(CODReconciliationError, match="Không có đơn hàng COD"):
        cod_reconciliation_generate(customer=customer_user, actor=customer_user)


def test_cod_reconciliation_full_lifecycle_and_selectors(customer_user, admin_user):
    """
    Test complete lifecycle: generate -> confirm -> mark_paid, and verify selector calculations.
    """
    # Create delivered COD orders
    o1 = order_create(
        customer=customer_user,
        sender_name="Sender 1",
        sender_phone="0901",
        sender_address="Hanoi",
        receiver_name="Receiver 1",
        receiver_phone="0902",
        receiver_address="HCM",
        cod_amount=Decimal("500000.00"),
        shipping_fee=Decimal("35000.00"),
        payment_method=OrderPaymentMethod.COD,
    )
    o1.status = OrderStatus.DELIVERED
    o1.save()

    o2 = order_create(
        customer=customer_user,
        sender_name="Sender 2",
        sender_phone="0903",
        sender_address="Hanoi",
        receiver_name="Receiver 2",
        receiver_phone="0904",
        receiver_address="Da Nang",
        cod_amount=Decimal("700000.00"),
        shipping_fee=Decimal("45000.00"),
        payment_method=OrderPaymentMethod.COD,
    )
    o2.status = OrderStatus.DELIVERED
    o2.save()

    # 1. Summary stats before reconciliation
    stats = cod_reconciliation_get_summary_stats(user=customer_user)
    assert stats["unreconciled_orders_count"] == 2
    assert stats["unreconciled_cod_total"] == Decimal("1200000.00")

    # 2. Generate statement
    rec = cod_reconciliation_generate(
        customer=customer_user,
        actor=customer_user,
        notes="Quyết toán đầu tháng",
    )
    assert rec.total_orders_count == 2
    assert rec.total_cod_amount == Decimal("1200000.00")
    assert rec.total_shipping_fees == Decimal("80000.00")
    assert rec.net_payout_amount == Decimal("1120000.00")
    assert rec.status == CODReconciliationStatus.PENDING

    # Orders should now have reconciliation FK
    o1.refresh_from_db()
    o2.refresh_from_db()
    assert o1.reconciliation_id == rec.id
    assert o2.reconciliation_id == rec.id

    # 3. Confirm statement
    rec_confirmed = cod_reconciliation_confirm(
        reconciliation=rec,
        actor=admin_user,
        notes="Số liệu chuẩn xác",
    )
    assert rec_confirmed.status == CODReconciliationStatus.CONFIRMED
    assert rec_confirmed.confirmed_at is not None

    # 4. Mark paid
    rec_paid = cod_reconciliation_mark_paid(
        reconciliation=rec_confirmed,
        actor=admin_user,
        notes="Chuyển khoản VCB thành công",
    )
    assert rec_paid.status == CODReconciliationStatus.PAID
    assert rec_paid.paid_at is not None

    # Orders payment_status should now be PAID
    o1.refresh_from_db()
    o2.refresh_from_db()
    assert o1.payment_status == OrderPaymentStatus.PAID
    assert o2.payment_status == OrderPaymentStatus.PAID

    # 5. Check selector list
    rec_list = cod_reconciliation_list(user=customer_user)
    assert rec_list.count() == 1
    assert rec_list.first().id == rec.id




