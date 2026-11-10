# mangementlogistics/orders/tests/test_views.py
from decimal import Decimal

from django.test import Client
from django.urls import reverse
import pytest

from mangementlogistics.orders.constants import (
    CODReconciliationStatus,
    OrderPaymentMethod,
    OrderStatus,
    ReturnFeePayer,
    ReturnReason,
    ReturnStatus,
    TripStatus,
    VehicleType,
)
from mangementlogistics.orders.services import (
    cod_reconciliation_generate,
    order_create,
)
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


def test_order_print_and_export_csv(client, customer_user):
    client.force_login(customer_user)
    order = order_create(
        customer=customer_user,
        sender_name="Sender Print",
        sender_phone="0911",
        sender_address="Hanoi",
        receiver_name="Receiver Print",
        receiver_phone="0922",
        receiver_address="HCM",
    )

    # Test Print View
    print_url = reverse("orders:order-print", kwargs={"order_id": order.id})
    resp_print = client.get(print_url)
    assert resp_print.status_code == 200
    assert "PHIẾU GIAO NHẬN BƯU KIỆN" in resp_print.content.decode("utf-8")
    assert order.tracking_number in resp_print.content.decode("utf-8")

    # Test CSV Export
    export_url = reverse("orders:order-export-csv")
    resp_export = client.get(export_url)
    assert resp_export.status_code == 200
    assert resp_export["Content-Type"].startswith("text/csv")
    content = resp_export.content.decode("utf-8")
    assert order.tracking_number in content
    assert "Mã vận đơn" in content


def test_order_fee_estimator_view_get(client):
    """
    Test public GET access to the shipping fee calculator page.
    """
    url = reverse("orders:fee-estimator")
    resp = client.get(url)
    assert resp.status_code == 200
    content = resp.content.decode("utf-8")
    assert "Tra cứu Giá cước & Thời gian giao hàng" in content
    assert "Thông số kiện hàng" in content
    assert "Giao Tiêu Chuẩn" in content


def test_order_fee_estimator_view_post_calculation(client):
    """
    Test POST submission on shipping fee calculator calculates and returns plan results.
    """
    url = reverse("orders:fee-estimator")
    payload = {
        "sender_province": "Hà Nội",
        "receiver_province": "Đà Nẵng",
        "weight": "2.5",
        "length": "30",
        "width": "20",
        "height": "10",
        "cod_amount": "500000",
    }
    resp = client.post(url, data=payload)
    assert resp.status_code == 200
    content = resp.content.decode("utf-8")
    assert "Hà Nội" in content
    assert "Đà Nẵng" in content
    assert "Liên miền" in content


def test_order_fee_estimator_view_ajax_json(client):
    """
    Test AJAX JSON endpoint for dynamic live recalculation.
    """
    url = reverse("orders:fee-estimator")
    params = {
        "sender_province": "Hà Nội",
        "receiver_province": "TP. Hồ Chí Minh",
        "weight": "1.0",
    }
    resp = client.get(url, data=params, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
    assert resp.status_code == 200
    json_data = resp.json()
    assert json_data["status"] == "success"
    assert json_data["data"]["route_type"] == "INTER_REGION"
    assert len(json_data["data"]["plans"]) == 3


def test_order_create_view_prefills_from_get_params(client, customer_user):
    """
    Test order create form pre-fills sender/receiver and shipping fee from GET query params.
    """
    client.force_login(customer_user)
    url = reverse("orders:order-create")
    params = {
        "weight": "3.5",
        "shipping_fee": "45000",
        "sender_address": "Hà Nội",
        "receiver_address": "TP. Hồ Chí Minh",
        "cod_amount": "200000",
        "notes": "Giao Hỏa Tốc",
    }
    resp = client.get(url, data=params)
    assert resp.status_code == 200
    content = resp.content.decode("utf-8")
    assert 'value="3.5"' in content
    assert 'value="45000"' in content
    assert 'value="200000"' in content


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(
        username="admin_view@example.com",
        email="admin_view@example.com",
        password="AdminPassword123!",
        name="Admin View User",
        role=UserRole.ADMIN,
    )


def test_cod_reconciliation_views_flow(client, customer_user, admin_user):
    """
    Test viewing list, generating statement, viewing detail, and processing by admin.
    """
    # 1. Unauthenticated redirects to login
    list_url = reverse("orders:reconciliation-list")
    resp = client.get(list_url)
    assert resp.status_code == 302
    assert "/users/login/" in resp.url

    # 2. Authenticated GET list view
    client.force_login(customer_user)
    resp_auth = client.get(list_url)
    assert resp_auth.status_code == 200
    assert "Quản lý Đối soát COD" in resp_auth.content.decode("utf-8")

    # 3. Create a delivered COD order
    order = order_create(
        customer=customer_user,
        sender_name="Sender Shop",
        sender_phone="0911",
        sender_address="Hanoi",
        receiver_name="Receiver Cust",
        receiver_phone="0922",
        receiver_address="HCM",
        cod_amount=Decimal("800000.00"),
        shipping_fee=Decimal("40000.00"),
        payment_method=OrderPaymentMethod.COD,
    )
    order.status = OrderStatus.DELIVERED
    order.save()

    # 4. GET generate form
    create_url = reverse("orders:reconciliation-create")
    resp_create_get = client.get(create_url)
    assert resp_create_get.status_code == 200
    assert "Lập kỳ đối soát COD mới" in resp_create_get.content.decode("utf-8")

    # 5. POST generate form
    resp_create_post = client.post(create_url, data={"notes": "Tuần 1"}, follow=True)
    assert resp_create_post.status_code == 200
    content = resp_create_post.content.decode("utf-8")
    assert "Bảng kê đối soát" in content
    assert "800.000" in content or "800000" in content

    # Get created reconciliation
    order.refresh_from_db()
    rec = order.reconciliation
    assert rec is not None
    assert rec.net_payout_amount == Decimal("760000.00")

    # 6. Admin processes (confirms) the statement
    client.force_login(admin_user)
    process_url = reverse("orders:reconciliation-process", kwargs={"reconciliation_id": rec.id})
    resp_process = client.post(
        process_url,
        data={"action": "CONFIRM", "notes": "Approved by accounting"},
        follow=True,
    )
    assert resp_process.status_code == 200
    rec.refresh_from_db()
    assert rec.status == CODReconciliationStatus.CONFIRMED

    # 7. Test Export CSV
    export_url = reverse("orders:reconciliation-export-csv", kwargs={"reconciliation_id": rec.id})
    resp_csv = client.get(export_url)
    assert resp_csv.status_code == 200
    assert resp_csv["Content-Type"].startswith("text/csv")
    csv_text = resp_csv.content.decode("utf-8")
    assert rec.code in csv_text
    assert order.tracking_number in csv_text
    assert "BẢNG KÊ ĐỐI SOÁT" in csv_text
    assert "TỔNG CỘNG" in csv_text


@pytest.fixture
def driver_user():
    return User.objects.create_user(
        username="driver_view@example.com",
        email="driver_view@example.com",
        password="DriverPassword123!",
        name="Driver View User",
        role=UserRole.DRIVER,
    )


def test_order_return_views_flow(client, customer_user, admin_user, driver_user):
    """
    Test viewing return list, creating return request, detail view, and admin/driver actions.
    """
    # 1. Unauthenticated redirects to login
    list_url = reverse("orders:return-list")
    resp_unauth = client.get(list_url)
    assert resp_unauth.status_code == 302
    assert "/users/login/" in resp_unauth.url

    # 2. Authenticated GET return list
    client.force_login(customer_user)
    resp_list = client.get(list_url)
    assert resp_list.status_code == 200
    assert "Quản lý Đơn hàng Hoàn trả (RMA)" in resp_list.content.decode("utf-8")

    # 3. Create an order for return
    order = order_create(
        customer=customer_user,
        sender_name="Sender RMA",
        sender_phone="0911",
        sender_address="Hanoi Hub",
        receiver_name="Receiver RMA",
        receiver_phone="0922",
        receiver_address="HCM Hub",
        cod_amount=Decimal("400000.00"),
        shipping_fee=Decimal("30000.00"),
    )

    # 4. GET return create form
    create_url = reverse("orders:order-return-create", kwargs={"order_id": order.id})
    resp_create_get = client.get(create_url)
    assert resp_create_get.status_code == 200
    assert "Tạo yêu cầu hoàn trả" in resp_create_get.content.decode("utf-8")

    # 5. POST return create form
    create_payload = {
        "reason": ReturnReason.WRONG_ITEM,
        "reason_detail": "Khách nhận sai size quần áo",
        "fee_payer": ReturnFeePayer.SHOP,
        "return_shipping_fee": "30000",
        "refund_amount": "400000",
        "return_address": "Hanoi Hub",
        "pickup_address": "HCM Hub",
        "notes": "Hàng nguyên tem",
    }
    resp_create_post = client.post(create_url, data=create_payload, follow=True)
    assert resp_create_post.status_code == 200
    content = resp_create_post.content.decode("utf-8")
    assert "Hồ sơ hoàn trả" in content

    # Get created return object
    ret = order.returns.first()
    assert ret is not None
    assert ret.status == ReturnStatus.REQUESTED

    # 6. Admin approves return and assigns driver
    client.force_login(admin_user)
    action_url = reverse("orders:return-action", kwargs={"return_id": ret.id})
    resp_approve = client.post(
        action_url,
        data={
            "action": "APPROVE",
            "driver": driver_user.id,
            "notes": "Chấp thuận thu hồi về kho",
        },
        follow=True,
    )
    assert resp_approve.status_code == 200
    ret.refresh_from_db()
    assert ret.status == ReturnStatus.APPROVED
    assert ret.assigned_driver_id == driver_user.id

    # 7. Driver updates status to PICKING_UP
    client.force_login(driver_user)
    resp_driver_update = client.post(
        action_url,
        data={
            "action": "UPDATE_STATUS",
            "status": ReturnStatus.PICKING_UP,
            "location": "Bưu cục phát",
            "notes": "Đang qua lấy hàng",
        },
        follow=True,
    )
    assert resp_driver_update.status_code == 200
    ret.refresh_from_db()
    assert ret.status == ReturnStatus.PICKING_UP

    # 8. Print RMA return slip view
    print_url = reverse("orders:return-print", kwargs={"return_id": ret.id})
    resp_print = client.get(print_url)
    assert resp_print.status_code == 200
    assert "PHIẾU THU HỒI & CHUYỂN HOÀN" in resp_print.content.decode("utf-8")
    assert ret.return_code in resp_print.content.decode("utf-8")


def test_delivery_trip_views_flow(client, customer_user, admin_user, driver_user):
    """
    Test viewing trip list, creating trip, adding orders, detail view, and dispatch action.
    """
    # 1. Unauthenticated redirects to login
    list_url = reverse("orders:trip-list")
    resp_unauth = client.get(list_url)
    assert resp_unauth.status_code == 302
    assert "/users/login/" in resp_unauth.url

    # 2. Driver GET trip list
    client.force_login(driver_user)
    resp_list = client.get(list_url)
    assert resp_list.status_code == 200
    assert "Quản lý Chuyến xe Giao hàng" in resp_list.content.decode("utf-8")

    # 3. GET create trip form
    create_url = reverse("orders:trip-create")
    resp_create_get = client.get(create_url)
    assert resp_create_get.status_code == 200

    # 4. POST create trip form
    create_payload = {
        "route_name": "Tuyến Hoàn Kiếm",
        "departure_hub": "Kho tổng Bờ Hồ",
        "vehicle_type": VehicleType.MOTORBIKE,
        "license_plate": "29B1-99999",
        "driver": driver_user.id,
        "notes": "Chuyến phát nhanh",
    }
    resp_create_post = client.post(create_url, data=create_payload)
    assert resp_create_post.status_code == 302

    from mangementlogistics.orders.models import DeliveryTrip
    trip = DeliveryTrip.objects.filter(driver=driver_user, route_name="Tuyến Hoàn Kiếm").first()
    assert trip is not None
    assert trip.status == TripStatus.PLANNED

    # 5. Create an order and add it to trip
    order = order_create(
        customer=customer_user,
        sender_name="Sender Shop",
        sender_phone="0911",
        sender_address="Hanoi",
        receiver_name="Receiver Test",
        receiver_phone="0922",
        receiver_address="Hoan Kiem",
        cod_amount=Decimal("150000.00"),
    )
    add_url = reverse("orders:trip-add-orders", kwargs={"trip_id": trip.id})
    resp_add_get = client.get(add_url)
    assert resp_add_get.status_code == 200

    resp_add_post = client.post(add_url, data={"orders": [order.id]})
    assert resp_add_post.status_code == 302

    trip.refresh_from_db()
    assert trip.status == TripStatus.LOADING
    assert trip.total_orders_count == 1

    # 6. GET trip detail view
    detail_url = reverse("orders:trip-detail", kwargs={"trip_id": trip.id})
    resp_detail = client.get(detail_url)
    assert resp_detail.status_code == 200
    assert trip.trip_code in resp_detail.content.decode("utf-8")

    # 7. Action: Dispatch trip
    action_url = reverse("orders:trip-action", kwargs={"trip_id": trip.id})
    resp_dispatch = client.post(
        action_url,
        data={
            "action": "DISPATCH",
            "notes": "Xe bắt đầu lăn bánh",
        },
    )
    assert resp_dispatch.status_code == 302
    trip.refresh_from_db()
    assert trip.status == TripStatus.IN_TRANSIT

    # 8. Print trip manifest run sheet view
    print_url = reverse("orders:trip-print", kwargs={"trip_id": trip.id})
    resp_print = client.get(print_url)
    assert resp_print.status_code == 200
    assert "BẢNG KÊ ĐIỀU PHỐI & XUẤT KHO" in resp_print.content.decode("utf-8")
    assert trip.trip_code in resp_print.content.decode("utf-8")









