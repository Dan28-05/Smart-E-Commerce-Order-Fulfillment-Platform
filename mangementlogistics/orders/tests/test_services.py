# mangementlogistics/orders/tests/test_services.py
from decimal import Decimal

import pytest

from mangementlogistics.orders.constants import (
    CODReconciliationStatus,
    OrderPaymentMethod,
    OrderPaymentStatus,
    OrderStatus,
    ReturnFeePayer,
    ReturnReason,
    ReturnStatus,
    TripStatus,
    VehicleType,
)
from mangementlogistics.orders.exceptions import (
    CODReconciliationError,
    DeliveryTripError,
    DriverAssignmentError,
    InvalidOrderStatusError,
    OrderPermissionDeniedError,
    OrderReturnError,
)
from mangementlogistics.orders.models import (
    CODReconciliation,
    DeliveryTrip,
    Order,
    OrderReturn,
)
from mangementlogistics.orders.selectors import (
    cod_reconciliation_get_summary_stats,
    cod_reconciliation_list,
    order_return_get_by_id,
    order_return_get_summary_stats,
    order_return_list,
)
from mangementlogistics.orders.services import (
    calculate_shipping_rates,
    cod_reconciliation_confirm,
    cod_reconciliation_generate,
    cod_reconciliation_mark_paid,
    delivery_trip_add_orders,
    delivery_trip_cancel,
    delivery_trip_complete,
    delivery_trip_create,
    delivery_trip_dispatch,
    delivery_trip_remove_order,
    order_add_checkpoint,
    order_cancel,
    order_create,
    order_delete,
    order_return_approve,
    order_return_create,
    order_return_reject,
    order_return_update_status,
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


def test_cod_reconciliation_end_to_end_delivery_to_payout(customer_user, driver_user, admin_user):
    """
    End-to-end integration test from order creation, driver delivery, reconciliation, to payout.
    """
    # 1. Shop creates COD order
    order = order_create(
        customer=customer_user,
        sender_name="Tech Store",
        sender_phone="0918112233",
        sender_address="123 Nguyen Trai, Ha Noi",
        receiver_name="Nguyen Van A",
        receiver_phone="0988776655",
        receiver_address="456 Le Loi, TP. HCM",
        weight=Decimal("1.5"),
        cod_amount=Decimal("1500000.00"),
        shipping_fee=Decimal("45000.00"),
        payment_method=OrderPaymentMethod.COD,
    )
    assert order.status == OrderStatus.PENDING
    assert order.reconciliation is None

    # 2. Admin confirms and assigns driver, then driver picks up and delivers
    order_update_status(
        order=order,
        new_status=OrderStatus.CONFIRMED,
        actor=admin_user,
        driver_id=driver_user.id,
        location="Trung tam dieu phoi",
        note="Xác nhận và phân công tài xế",
    )
    order_update_status(
        order=order,
        new_status=OrderStatus.PICKED_UP,
        actor=driver_user,
        location="Kho Ha Noi",
        note="Đã nhận bưu kiện từ shop",
    )
    order_update_status(
        order=order,
        new_status=OrderStatus.DELIVERED,
        actor=driver_user,
        location="Quan 1, TP. HCM",
        note="Phát hàng thành công và đã thu tiền COD",
    )
    order.refresh_from_db()
    assert order.status == OrderStatus.DELIVERED
    assert order.delivered_at is not None

    # 3. Customer checks eligible orders and generates statement
    from mangementlogistics.orders.selectors import cod_reconciliation_get_eligible_orders
    eligible = cod_reconciliation_get_eligible_orders(customer=customer_user)
    assert eligible.filter(id=order.id).exists()

    rec = cod_reconciliation_generate(
        customer=customer_user,
        actor=customer_user,
        notes="Kỳ đối soát tự động cuối tuần",
    )
    assert rec.total_orders_count == 1
    assert rec.total_cod_amount == Decimal("1500000.00")
    assert rec.total_shipping_fees == Decimal("45000.00")
    assert rec.net_payout_amount == Decimal("1455000.00")
    assert rec.status == CODReconciliationStatus.PENDING

    # 4. Admin marks paid
    cod_reconciliation_mark_paid(
        reconciliation=rec,
        actor=admin_user,
        notes="Chuyển khoản thành công vào STK MBBank của shop",
    )
    rec.refresh_from_db()
    order.refresh_from_db()
    assert rec.status == CODReconciliationStatus.PAID
    assert order.payment_status == OrderPaymentStatus.PAID


def test_order_return_model_defaults(customer_user):
    """
    Test OrderReturn model creation, generated code, and initial status.
    """
    order = order_create(
        customer=customer_user,
        sender_name="Sender",
        sender_phone="0901",
        sender_address="Hanoi",
        receiver_name="Receiver",
        receiver_phone="0902",
        receiver_address="HCM",
        cod_amount=Decimal("300000.00"),
        shipping_fee=Decimal("30000.00"),
    )
    ret = OrderReturn.objects.create(
        order=order,
        requested_by=customer_user,
        reason=ReturnReason.WRONG_ITEM,
        reason_detail="Khách báo nhận sai màu áo",
        fee_payer=ReturnFeePayer.SHOP,
        return_shipping_fee=Decimal("25000.00"),
        refund_amount=Decimal("300000.00"),
    )
    assert ret.return_code.startswith("RET-")
    assert ret.status == ReturnStatus.REQUESTED
    assert ret.order_id == order.id
    assert ret.refund_amount == Decimal("300000.00")
    assert str(ret).startswith(ret.return_code)


def test_order_return_create_success(customer_user):
    """
    Test creating an order return request successfully.
    """
    order = order_create(
        customer=customer_user,
        sender_name="Shop Test",
        sender_phone="0911",
        sender_address="Hanoi",
        receiver_name="Receiver Test",
        receiver_phone="0922",
        receiver_address="HCM",
        cod_amount=Decimal("500000.00"),
        shipping_fee=Decimal("35000.00"),
    )
    ret = order_return_create(
        order=order,
        actor=customer_user,
        reason=ReturnReason.DAMAGED,
        reason_detail="Vỡ hộp khi vận chuyển",
    )
    assert ret.status == ReturnStatus.REQUESTED
    assert ret.order_id == order.id
    assert ret.return_shipping_fee == Decimal("35000.00")
    assert order.tracking_history.filter(note__icontains=ret.return_code).exists()


def test_order_return_create_duplicate_raises_error(customer_user):
    """
    Ensure cannot create multiple active returns for the same order.
    """
    order = order_create(
        customer=customer_user,
        sender_name="Shop Test",
        sender_phone="0911",
        sender_address="Hanoi",
        receiver_name="Receiver Test",
        receiver_phone="0922",
        receiver_address="HCM",
    )
    order_return_create(
        order=order,
        actor=customer_user,
        reason=ReturnReason.WRONG_ITEM,
    )
    with pytest.raises(OrderReturnError, match="đã có một yêu cầu hoàn trả"):
        order_return_create(
            order=order,
            actor=customer_user,
            reason=ReturnReason.OTHER,
        )


def test_order_return_approve_and_reject(customer_user, admin_user, driver_user):
    """
    Test admin approving with driver assignment and admin rejecting.
    """
    order = order_create(
        customer=customer_user,
        sender_name="Shop Test",
        sender_phone="0911",
        sender_address="Hanoi",
        receiver_name="Receiver Test",
        receiver_phone="0922",
        receiver_address="HCM",
    )
    ret = order_return_create(
        order=order,
        actor=customer_user,
        reason=ReturnReason.CUSTOMER_REFUSED,
    )

    # 1. Non-admin cannot approve
    with pytest.raises(OrderPermissionDeniedError):
        order_return_approve(order_return=ret, actor=customer_user)

    # 2. Admin approves
    approved_ret = order_return_approve(
        order_return=ret,
        actor=admin_user,
        driver_id=driver_user.id,
        notes="Chấp thuận thu hồi",
    )
    assert approved_ret.status == ReturnStatus.APPROVED
    assert approved_ret.assigned_driver_id == driver_user.id
    assert approved_ret.approved_at is not None

    # Test reject on fresh return
    order2 = order_create(
        customer=customer_user,
        sender_name="Shop 2",
        sender_phone="0911",
        sender_address="Hanoi",
        receiver_name="Receiver 2",
        receiver_phone="0922",
        receiver_address="HCM",
    )
    ret2 = order_return_create(
        order=order2,
        actor=customer_user,
        reason=ReturnReason.OTHER,
    )
    rejected_ret = order_return_reject(
        order_return=ret2,
        actor=admin_user,
        reason="Không đủ điều kiện đổi trả theo quy định shop",
    )
    assert rejected_ret.status == ReturnStatus.REJECTED
    assert "Không đủ điều kiện" in rejected_ret.notes


def test_order_return_driver_status_pipeline(customer_user, admin_user, driver_user):
    """
    Test driver updating return status along reverse pipeline.
    """
    order = order_create(
        customer=customer_user,
        sender_name="Shop Test",
        sender_phone="0911",
        sender_address="Hanoi",
        receiver_name="Receiver Test",
        receiver_phone="0922",
        receiver_address="HCM",
    )
    ret = order_return_create(
        order=order,
        actor=customer_user,
        reason=ReturnReason.CUSTOMER_REQUESTED,
    )
    order_return_approve(order_return=ret, actor=admin_user, driver_id=driver_user.id)

    # Driver updates to PICKING_UP
    order_return_update_status(
        order_return=ret,
        new_status=ReturnStatus.PICKING_UP,
        actor=driver_user,
        location="Quan 1, HCM",
        note="Đến lấy hàng từ khách",
    )
    ret.refresh_from_db()
    assert ret.status == ReturnStatus.PICKING_UP

    # Driver updates to IN_RETURN_TRANSIT -> master order status changes to RETURNED
    order_return_update_status(
        order_return=ret,
        new_status=ReturnStatus.IN_RETURN_TRANSIT,
        actor=driver_user,
        location="Hub Trung Chuyen",
        note="Đã đưa về kho trung chuyển",
    )
    ret.refresh_from_db()
    order.refresh_from_db()
    assert ret.status == ReturnStatus.IN_RETURN_TRANSIT
    assert order.status == OrderStatus.RETURNED

    # Driver completes return to sender
    order_return_update_status(
        order_return=ret,
        new_status=ReturnStatus.RETURNED_TO_SENDER,
        actor=driver_user,
        location="Kho Shop, Hanoi",
        note="Giao trả hàng thành công cho shop",
    )
    ret.refresh_from_db()
    assert ret.status == ReturnStatus.RETURNED_TO_SENDER
    assert ret.completed_at is not None


def test_order_return_selectors_filtering_and_stats(customer_user, admin_user, driver_user):
    """
    Test order return selectors for role-based scoping, status filtering, search, and summary stats.
    """
    order1 = order_create(
        customer=customer_user,
        sender_name="Sender Shop A",
        sender_phone="0901",
        sender_address="Hanoi",
        receiver_name="Receiver A",
        receiver_phone="0902",
        receiver_address="HCM",
    )
    ret1 = order_return_create(
        order=order1,
        actor=customer_user,
        reason=ReturnReason.DAMAGED,
        reason_detail="Hàng móp méo",
        refund_amount=Decimal("200000.00"),
    )
    order_return_approve(order_return=ret1, actor=admin_user, driver_id=driver_user.id)

    order2 = order_create(
        customer=customer_user,
        sender_name="Sender Shop B",
        sender_phone="0903",
        sender_address="Hanoi",
        receiver_name="Receiver B",
        receiver_phone="0904",
        receiver_address="Da Nang",
    )
    ret2 = order_return_create(
        order=order2,
        actor=customer_user,
        reason=ReturnReason.CUSTOMER_REFUSED,
        reason_detail="Người nhận không có nhà",
    )

    # 1. Customer selector list
    cust_list = order_return_list(user=customer_user)
    assert cust_list.count() == 2

    # 2. Driver selector list (only assigned ret1)
    driver_list = order_return_list(user=driver_user)
    assert driver_list.count() == 1
    assert driver_list.first().id == ret1.id

    # 3. Search filter
    search_res = order_return_list(user=admin_user, search="móp méo")
    assert search_res.count() == 1
    assert search_res.first().id == ret1.id

    # 4. Status filter
    pending_list = order_return_list(user=admin_user, status=ReturnStatus.REQUESTED)
    assert pending_list.count() == 1
    assert pending_list.first().id == ret2.id

    # 5. Get by ID
    found_ret = order_return_get_by_id(return_id=ret1.id, user=customer_user)
    assert found_ret is not None
    assert found_ret.id == ret1.id

    # 6. Summary stats
    stats = order_return_get_summary_stats(user=admin_user)
    assert stats["total_returns"] == 2
    assert stats["pending_requested"] == 1
    assert stats["in_transit_returns"] == 1
    assert stats["total_refund_amount"] == Decimal("200000.00")


def test_order_return_full_reverse_logistics_e2e_flow(customer_user, admin_user, driver_user):
    """
    End-to-End test covering the complete reverse logistics lifecycle:
    Order Creation -> Delivery -> Return Request -> Approval & Driver Assignment ->
    Pickup -> In Transit -> Master Order Status Synchronization -> Completed Return to Sender.
    """
    # Step 1: Create master order
    order = order_create(
        customer=customer_user,
        sender_name="Tech Store Hanoi",
        sender_phone="0911223344",
        sender_address="123 Cau Giay, Hanoi",
        receiver_name="Nguyen Van A",
        receiver_phone="0988776655",
        receiver_address="456 Nguyen Trai, Q1, HCM",
        weight=Decimal("1.5"),
        cod_amount=Decimal("600000.00"),
        shipping_fee=Decimal("35000.00"),
    )
    assert order.status == OrderStatus.PENDING

    # Step 2: Forward delivery cycle
    order_update_status(
        order=order,
        new_status=OrderStatus.CONFIRMED,
        actor=admin_user,
        driver_id=driver_user.id,
        location="Trung tâm điều phối",
        note="Phân công tài xế giao",
    )
    order_update_status(
        order=order,
        new_status=OrderStatus.PICKED_UP,
        actor=driver_user,
        location="Kho Ha Noi",
        note="Đã tiếp nhận hàng",
    )
    order_update_status(
        order=order,
        new_status=OrderStatus.DELIVERED,
        actor=driver_user,
        location="Quan 1, HCM",
        note="Giao thành công cho khách hàng",
    )
    order.refresh_from_db()
    assert order.status == OrderStatus.DELIVERED

    # Step 3: Initiate reverse logistics (Return Request)
    order_return = order_return_create(
        order=order,
        actor=customer_user,
        reason=ReturnReason.DAMAGED,
        reason_detail="Sản phẩm bị lỗi nguồn không hoạt động",
        return_shipping_fee=Decimal("35000.00"),
        refund_amount=Decimal("600000.00"),
        fee_payer=ReturnFeePayer.SHOP,
        pickup_address=order.receiver_address,
        return_address=order.sender_address,
    )
    assert order_return.status == ReturnStatus.REQUESTED
    assert order_return.return_code.startswith("RET-")

    # Step 4: Admin reviews and approves return
    order_return_approve(
        order_return=order_return,
        actor=admin_user,
        driver_id=driver_user.id,
        notes="Chấp nhận yêu cầu đổi trả bảo hành",
    )
    order_return.refresh_from_db()
    assert order_return.status == ReturnStatus.APPROVED
    assert order_return.assigned_driver_id == driver_user.id
    assert order_return.approved_at is not None

    # Step 5: Driver picks up the return package
    order_return_update_status(
        order_return=order_return,
        new_status=ReturnStatus.PICKING_UP,
        actor=driver_user,
        location="Quan 1, HCM",
        note="Tài xế đã đến lấy bưu phẩm hoàn",
    )
    order_return.refresh_from_db()
    assert order_return.status == ReturnStatus.PICKING_UP

    # Step 6: Driver transfers package into transit (Master order status syncs to RETURNED)
    order_return_update_status(
        order_return=order_return,
        new_status=ReturnStatus.IN_RETURN_TRANSIT,
        actor=driver_user,
        location="Trung tâm khai thác miền Nam",
        note="Đang vận chuyển hoàn về kho Hà Nội",
    )
    order_return.refresh_from_db()
    order.refresh_from_db()
    assert order_return.status == ReturnStatus.IN_RETURN_TRANSIT
    assert order.status == OrderStatus.RETURNED

    # Step 7: Completed delivery back to sender
    order_return_update_status(
        order_return=order_return,
        new_status=ReturnStatus.RETURNED_TO_SENDER,
        actor=driver_user,
        location="123 Cau Giay, Hanoi",
        note="Đã bàn giao bưu kiện hoàn trả cho shop",
    )
    order_return.refresh_from_db()
    assert order_return.status == ReturnStatus.RETURNED_TO_SENDER
    assert order_return.completed_at is not None

    # Step 8: Verify KPI summary reflects completed reverse logistics
    final_stats = order_return_get_summary_stats(user=customer_user)
    assert final_stats["total_returns"] >= 1
    assert final_stats["completed_returns"] >= 1
    assert final_stats["total_refund_amount"] >= Decimal("600000.00")


def test_delivery_trip_model_defaults(driver_user, admin_user, customer_user):
    """
    Test DeliveryTrip model creation, generated trip code, vehicle defaults and relationships.
    """
    trip = DeliveryTrip.objects.create(
        driver=driver_user,
        created_by=admin_user,
        route_name="Tuyến Hà Nội - Bắc Ninh",
        departure_hub="Kho tổng Gia Lâm",
        vehicle_type=VehicleType.VAN,
        license_plate="29D-888.99",
    )
    assert trip.id is not None
    assert trip.trip_code.startswith("TRIP-")
    assert trip.status == TripStatus.PLANNED
    assert trip.total_orders_count == 0
    assert trip.total_weight == 0
    assert trip.total_cod_amount == 0
    assert trip.completion_rate == 0
    assert trip.route_name in str(trip)

    # Attach order to trip
    order = order_create(
        customer=customer_user,
        sender_name="Sender",
        sender_phone="0901",
        sender_address="Hanoi",
        receiver_name="Receiver",
        receiver_phone="0902",
        receiver_address="Bac Ninh",
        weight=Decimal("2.5"),
        cod_amount=Decimal("250000.00"),
        shipping_fee=Decimal("30000.00"),
    )
    order.delivery_trip = trip
    order.save()

    assert trip.total_orders_count == 1
    assert trip.total_weight == Decimal("2.5")
    assert trip.total_cod_amount == Decimal("250000.00")


def test_delivery_trip_create_and_validation(driver_user, admin_user, customer_user):
    """
    Test delivery trip creation validation rules, roles and permissions.
    """
    # 1. Customer cannot create delivery trip
    with pytest.raises(OrderPermissionDeniedError):
        delivery_trip_create(
            driver=driver_user,
            actor=customer_user,
            route_name="Tuyến Ba Đình",
        )

    # 2. Assigning non-driver raises DeliveryTripError
    with pytest.raises(DeliveryTripError):
        delivery_trip_create(
            driver=customer_user,
            actor=admin_user,
            route_name="Tuyến Ba Đình",
        )

    # 3. Empty route name raises DeliveryTripError
    with pytest.raises(DeliveryTripError):
        delivery_trip_create(
            driver=driver_user,
            actor=driver_user,
            route_name="   ",
        )

    # 4. Driver successfully creates own trip
    trip = delivery_trip_create(
        driver=driver_user,
        actor=driver_user,
        route_name="Tuyến Đống Đa - Hoàn Kiếm",
        departure_hub="Bưu cục Đống Đa",
        vehicle_type=VehicleType.MOTORBIKE,
        license_plate="29E1-12345",
    )
    assert trip.status == TripStatus.PLANNED
    assert trip.driver == driver_user
    assert trip.license_plate == "29E1-12345"


def test_delivery_trip_add_remove_orders_flow(driver_user, admin_user, customer_user):
    """
    Test batch adding orders to a trip and removing orders.
    """
    trip = delivery_trip_create(
        driver=driver_user,
        actor=admin_user,
        route_name="Tuyến Cầu Giấy",
        departure_hub="Kho tổng Cầu Giấy",
    )
    assert trip.status == TripStatus.PLANNED

    order1 = order_create(
        customer=customer_user,
        sender_name="Sender 1",
        sender_phone="0901",
        sender_address="Hanoi",
        receiver_name="Receiver 1",
        receiver_phone="0902",
        receiver_address="Cau Giay",
        weight=Decimal("1.0"),
        cod_amount=Decimal("100000.00"),
    )
    order2 = order_create(
        customer=customer_user,
        sender_name="Sender 2",
        sender_phone="0903",
        sender_address="Hanoi",
        receiver_name="Receiver 2",
        receiver_phone="0904",
        receiver_address="Cau Giay",
        weight=Decimal("2.0"),
        cod_amount=Decimal("200000.00"),
    )

    # 1. Add orders to trip
    updated = delivery_trip_add_orders(
        trip=trip,
        order_ids=[order1.id, order2.id],
        actor=driver_user,
    )
    assert len(updated) == 2
    trip.refresh_from_db()
    assert trip.status == TripStatus.LOADING
    assert trip.total_orders_count == 2
    assert trip.total_cod_amount == Decimal("300000.00")

    order1.refresh_from_db()
    assert order1.delivery_trip_id == trip.id
    assert order1.driver_id == driver_user.id
    assert order1.status == OrderStatus.CONFIRMED

    # 2. Remove order1 from trip
    delivery_trip_remove_order(trip=trip, order_id=order1.id, actor=driver_user)
    trip.refresh_from_db()
    assert trip.total_orders_count == 1

    order1.refresh_from_db()
    assert order1.delivery_trip is None


def test_delivery_trip_dispatch_complete_and_cancel_lifecycle(driver_user, admin_user, customer_user):
    """
    Test trip dispatching (batch status update to IN_TRANSIT), completion and cancellation.
    """
    trip = delivery_trip_create(
        driver=driver_user,
        actor=admin_user,
        route_name="Tuyến Hai Bà Trưng",
    )

    # 1. Cannot dispatch empty trip
    with pytest.raises(DeliveryTripError):
        delivery_trip_dispatch(trip=trip, actor=driver_user)

    order = order_create(
        customer=customer_user,
        sender_name="Sender",
        sender_phone="0901",
        sender_address="Hanoi",
        receiver_name="Receiver",
        receiver_phone="0902",
        receiver_address="HBT",
        weight=Decimal("1.5"),
        cod_amount=Decimal("500000.00"),
    )
    delivery_trip_add_orders(trip=trip, order_ids=[order.id], actor=admin_user)

    # 2. Dispatch trip
    delivery_trip_dispatch(trip=trip, actor=driver_user, notes="Bắt đầu giao đơn")
    trip.refresh_from_db()
    assert trip.status == TripStatus.IN_TRANSIT
    assert trip.departure_time is not None

    order.refresh_from_db()
    assert order.status == OrderStatus.IN_TRANSIT

    # 3. Complete trip
    delivery_trip_complete(trip=trip, actor=driver_user, notes="Đã giao hết tuyến")
    trip.refresh_from_db()
    assert trip.status == TripStatus.COMPLETED
    assert trip.completion_time is not None

    # 4. Cancel a planned trip with attached orders
    trip2 = delivery_trip_create(
        driver=driver_user,
        actor=admin_user,
        route_name="Tuyến Hoàng Mai",
    )
    order2 = order_create(
        customer=customer_user,
        sender_name="Sender 2",
        sender_phone="0903",
        sender_address="Hanoi",
        receiver_name="Receiver 2",
        receiver_phone="0904",
        receiver_address="Hoang Mai",
    )
    delivery_trip_add_orders(trip=trip2, order_ids=[order2.id], actor=admin_user)
    delivery_trip_cancel(trip=trip2, actor=admin_user, reason="Tài xế có việc bận đột xuất")
    trip2.refresh_from_db()
    assert trip2.status == TripStatus.CANCELLED
    order2.refresh_from_db()
    assert order2.delivery_trip is None











