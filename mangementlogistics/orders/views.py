# mangementlogistics/orders/views.py
import csv

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from mangementlogistics.orders.constants import VIETNAM_PROVINCES
from mangementlogistics.orders.exceptions import (
    DriverAssignmentError,
    InvalidOrderStatusError,
    OrderPermissionDeniedError,
)
from mangementlogistics.orders.forms import (
    OrderCancelForm,
    OrderCheckpointForm,
    OrderCreateForm,
    OrderStatusUpdateForm,
    OrderUpdateForm,
    ShippingFeeEstimatorForm,
)
from mangementlogistics.orders.models import Order
from mangementlogistics.orders.selectors import (
    order_get_by_id,
    order_get_by_tracking_number,
    order_get_tracking_history,
    order_list,
)
from mangementlogistics.orders.services import (
    calculate_shipping_rates,
    order_add_checkpoint,
    order_cancel,
    order_create,
    order_delete,
    order_update,
    order_update_status,
)
from mangementlogistics.users.constants import UserRole


def order_list_view(request):
    """
    Renders the order list dashboard tailored to the authenticated user.
    """
    if not request.user.is_authenticated:
        messages.info(request, "Vui lòng đăng nhập hoặc sử dụng tính năng tra cứu đơn hàng công khai bên dưới.")
        return redirect("orders:order-track")

    status_filter = request.GET.get("status") or None
    search_query = request.GET.get("search") or None

    orders = order_list(
        user=request.user,
        status=status_filter,
        search=search_query,
    )

    return render(
        request,
        "orders/order_list.html",
        {
            "orders": orders,
            "selected_status": status_filter,
            "search_query": search_query or "",
            "is_admin": request.user.is_superuser or getattr(request.user, "role", None) == UserRole.ADMIN,
            "is_driver": getattr(request.user, "role", None) == UserRole.DRIVER,
        },
    )


def order_create_view(request):
    """
    Renders and processes the form to create a new delivery order.
    """
    if not request.user.is_authenticated:
        messages.error(request, "Vui lòng đăng nhập để tạo đơn hàng.")
        return redirect("home")

    if request.method == "POST":
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            try:
                order = order_create(
                    customer=request.user,
                    **form.cleaned_data,
                )
                messages.success(request, f"Tạo đơn hàng thành công! Mã vận đơn của bạn: {order.tracking_number}")
                return redirect("orders:order-detail", order_id=order.id)
            except Exception as exc:
                messages.error(request, f"Lỗi tạo đơn hàng: {exc}")
    else:
        # Pre-fill sender details from customer profile and query params if provided
        initial_data = {
            "sender_name": request.user.name or "",
            "sender_phone": request.user.phone_number or "",
            "sender_address": request.GET.get("sender_address") or request.user.address or "",
            "receiver_address": request.GET.get("receiver_address") or "",
            "weight": request.GET.get("weight") or 1.0,
            "shipping_fee": request.GET.get("shipping_fee") or 0,
            "cod_amount": request.GET.get("cod_amount") or 0,
            "notes": request.GET.get("notes") or "",
        }
        form = OrderCreateForm(initial=initial_data)

    return render(
        request,
        "orders/order_form.html",
        {"form": form, "action_title": "Tạo đơn hàng mới"},
    )


def order_detail_view(request, order_id: int):
    """
    Renders full details of an order with actions to update status, edit, or cancel.
    """
    order = order_get_by_id(order_id=order_id, user=request.user)
    if not order:
        messages.error(request, "Không tìm thấy đơn hàng hoặc bạn không có quyền xem đơn hàng này.")
        return redirect("orders:order-list")

    is_admin = request.user.is_superuser or getattr(request.user, "role", None) == UserRole.ADMIN
    is_driver = getattr(request.user, "role", None) == UserRole.DRIVER and order.driver_id == request.user.id

    tracking_history = order_get_tracking_history(order=order)

    status_form = None
    checkpoint_form = None
    if is_admin or is_driver:
        status_form = OrderStatusUpdateForm(
            initial={
                "status": order.status,
                "driver": order.driver,
            }
        )
        checkpoint_form = OrderCheckpointForm()

    return render(
        request,
        "orders/order_detail.html",
        {
            "order": order,
            "is_admin": is_admin,
            "is_driver": is_driver,
            "status_form": status_form,
            "checkpoint_form": checkpoint_form,
            "tracking_history": tracking_history,
            "can_cancel": order.can_be_cancelled(),
        },
    )


def order_update_view(request, order_id: int):
    """
    Allows editing order details while it is pending.
    """
    order = order_get_by_id(order_id=order_id, user=request.user)
    if not order:
        messages.error(request, "Không tìm thấy đơn hàng hoặc bạn không có quyền chỉnh sửa.")
        return redirect("orders:order-list")

    if request.method == "POST":
        form = OrderUpdateForm(request.POST, instance=order)
        if form.is_valid():
            try:
                order_update(order=order, actor=request.user, **form.cleaned_data)
                messages.success(request, "Cập nhật thông tin đơn hàng thành công!")
                return redirect("orders:order-detail", order_id=order.id)
            except (OrderPermissionDeniedError, DriverAssignmentError) as exc:
                messages.error(request, str(exc))
    else:
        form = OrderUpdateForm(instance=order)

    return render(
        request,
        "orders/order_form.html",
        {
            "form": form,
            "order": order,
            "action_title": f"Chỉnh sửa đơn hàng #{order.tracking_number}",
        },
    )


def order_status_update_view(request, order_id: int):
    """
    View to process status change and driver assignment from detail page.
    """
    if request.method != "POST":
        return redirect("orders:order-detail", order_id=order_id)

    order = order_get_by_id(order_id=order_id, user=request.user)
    if not order:
        messages.error(request, "Không tìm thấy đơn hàng.")
        return redirect("orders:order-list")

    form = OrderStatusUpdateForm(request.POST)
    if form.is_valid():
        new_status = form.cleaned_data["status"]
        location = form.cleaned_data.get("location", "")
        note = form.cleaned_data.get("note", "")
        driver = form.cleaned_data.get("driver")
        driver_id = driver.id if driver else None

        try:
            order_update_status(
                order=order,
                new_status=new_status,
                actor=request.user,
                driver_id=driver_id,
                location=location,
                note=note,
            )
            messages.success(request, f"Cập nhật trạng thái sang '{order.get_status_display()}' thành công!")
        except (InvalidOrderStatusError, OrderPermissionDeniedError, DriverAssignmentError) as exc:
            messages.error(request, str(exc))

    return redirect("orders:order-detail", order_id=order.id)


def order_add_checkpoint_view(request, order_id: int):
    """
    View for drivers or admins to append a checkpoint along the delivery journey.
    """
    if request.method != "POST":
        return redirect("orders:order-detail", order_id=order_id)

    order = order_get_by_id(order_id=order_id, user=request.user)
    if not order:
        messages.error(request, "Không tìm thấy đơn hàng.")
        return redirect("orders:order-list")

    form = OrderCheckpointForm(request.POST)
    if form.is_valid():
        location = form.cleaned_data["location"]
        note = form.cleaned_data["note"]
        try:
            order_add_checkpoint(
                order=order,
                location=location,
                note=note,
                actor=request.user,
            )
            messages.success(request, f"Đã ghi nhận mốc hành trình tại '{location}'.")
        except OrderPermissionDeniedError as exc:
            messages.error(request, str(exc))

    return redirect("orders:order-detail", order_id=order.id)


def order_print_view(request, order_id: int):
    """
    Renders a printable shipping label / Airway Bill (AWB) formatted for thermal/A5 printers.
    """
    order = order_get_by_id(order_id=order_id, user=request.user)
    if not order:
        messages.error(request, "Không tìm thấy đơn hàng để in phiếu gửi.")
        return redirect("orders:order-list")

    return render(
        request,
        "orders/order_print.html",
        {
            "order": order,
        },
    )


def order_export_csv_view(request):
    """
    Exports filtered orders to a CSV file with UTF-8 BOM encoding for Microsoft Excel compatibility.
    """
    if not request.user.is_authenticated:
        messages.error(request, "Vui lòng đăng nhập để xuất dữ liệu.")
        return redirect("users:login")

    status = request.GET.get("status") or None
    search = request.GET.get("search") or None
    orders = order_list(user=request.user, status=status, search=search)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="danh_sach_don_hang.csv"'

    # Write UTF-8 BOM so Vietnamese characters display properly in Excel
    response.write("\ufeff".encode("utf-8"))

    writer = csv.writer(response)
    writer.writerow([
        "Mã vận đơn",
        "Người gửi",
        "SĐT gửi",
        "Địa chỉ gửi",
        "Người nhận",
        "SĐT nhận",
        "Địa chỉ nhận",
        "Trọng lượng (kg)",
        "Tiền thu hộ COD (VNĐ)",
        "Cước phí (VNĐ)",
        "Tổng tiền (VNĐ)",
        "Phương thức thanh toán",
        "Trạng thái thanh toán",
        "Trạng thái đơn hàng",
        "Tài xế phụ trách",
        "Ngày tạo",
    ])

    for o in orders:
        writer.writerow([
            o.tracking_number,
            o.sender_name,
            o.sender_phone,
            o.sender_address,
            o.receiver_name,
            o.receiver_phone,
            o.receiver_address,
            o.weight,
            int(o.cod_amount),
            int(o.shipping_fee),
            int(o.total_amount),
            o.get_payment_method_display(),
            o.get_payment_status_display(),
            o.get_status_display(),
            o.driver.name if o.driver else "Chưa phân công",
            o.created_at.strftime("%d/%m/%Y %H:%M"),
        ])

    return response



def order_cancel_view(request, order_id: int):
    """
    View for customer or admin to cancel an order.
    """
    order = order_get_by_id(order_id=order_id, user=request.user)
    if not order:
        messages.error(request, "Không tìm thấy đơn hàng.")
        return redirect("orders:order-list")

    if request.method == "POST":
        form = OrderCancelForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data.get("reason", "")
            try:
                order_cancel(order=order, actor=request.user, reason=reason)
                messages.success(request, f"Đơn hàng #{order.tracking_number} đã được hủy thành công.")
                return redirect("orders:order-detail", order_id=order.id)
            except (InvalidOrderStatusError, OrderPermissionDeniedError) as exc:
                messages.error(request, str(exc))
    else:
        form = OrderCancelForm()

    return render(
        request,
        "orders/order_cancel.html",
        {"order": order, "form": form},
    )


def order_delete_view(request, order_id: int):
    """
    View to delete an order.
    """
    if request.method == "POST":
        order = order_get_by_id(order_id=order_id, user=request.user)
        if not order:
            messages.error(request, "Không tìm thấy đơn hàng.")
            return redirect("orders:order-list")

        try:
            order_delete(order=order, actor=request.user)
            messages.success(request, "Đã xóa đơn hàng thành công.")
        except OrderPermissionDeniedError as exc:
            messages.error(request, str(exc))

    return redirect("orders:order-list")


def order_track_view(request):
    """
    Public tracking view: user inputs tracking number to check progress and milestone history.
    """
    tracking_number = request.GET.get("tracking") or ""
    order = None
    not_found = False
    tracking_history = None

    if tracking_number:
        order = order_get_by_tracking_number(tracking_number=tracking_number)
        if not order:
            not_found = True
        else:
            tracking_history = order_get_tracking_history(order=order)

    return render(
        request,
        "orders/order_track.html",
        {
            "tracking_number": tracking_number,
            "order": order,
            "not_found": not_found,
            "tracking_history": tracking_history,
        },
    )


def order_fee_estimator_view(request):
    """
    Renders the interactive shipping fee and delivery time estimator.
    Supports standard GET/POST form submissions as well as AJAX JSON requests.
    """
    result = None
    form = None

    if request.method == "POST":
        form = ShippingFeeEstimatorForm(request.POST)
        if form.is_valid():
            result = calculate_shipping_rates(**form.cleaned_data)
    elif request.GET.get("sender_province") and request.GET.get("receiver_province"):
        form = ShippingFeeEstimatorForm(request.GET)
        if form.is_valid():
            result = calculate_shipping_rates(**form.cleaned_data)
    else:
        # Default estimation initial state: Hanoi to HCMC, 1kg
        default_sender = "Hà Nội"
        default_receiver = "TP. Hồ Chí Minh"
        if request.user.is_authenticated and getattr(request.user, "address", None):
            for prov in VIETNAM_PROVINCES:
                if prov in request.user.address:
                    default_sender = prov
                    break

        form = ShippingFeeEstimatorForm(
            initial={
                "sender_province": default_sender,
                "receiver_province": default_receiver,
                "weight": 1.0,
                "cod_amount": 0,
            }
        )
        result = calculate_shipping_rates(
            sender_province=default_sender,
            receiver_province=default_receiver,
            weight=1.0,
            length=0,
            width=0,
            height=0,
            cod_amount=0,
        )

    # AJAX JSON response support for interactive calculators
    if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.GET.get("format") == "json":
        if result:
            return JsonResponse({"status": "success", "data": result})
        return JsonResponse({"status": "error", "errors": form.errors if form else "Invalid payload"}, status=400)

    return render(
        request,
        "orders/fee_estimator.html",
        {
            "form": form,
            "result": result,
        },
    )

