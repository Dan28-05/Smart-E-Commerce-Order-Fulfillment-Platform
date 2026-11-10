# mangementlogistics/orders/views.py
import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from mangementlogistics.orders.constants import (
    CODReconciliationStatus,
    OrderStatus,
    ReturnFeePayer,
    ReturnReason,
    ReturnStatus,
    TripStatus,
    VIETNAM_PROVINCES,
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
from mangementlogistics.orders.forms import (
    CODReconciliationGenerateForm,
    CODReconciliationProcessForm,
    DeliveryTripActionForm,
    DeliveryTripAddOrdersForm,
    DeliveryTripCreateForm,
    OrderCancelForm,
    OrderCheckpointForm,
    OrderCreateForm,
    OrderReturnActionForm,
    OrderReturnCreateForm,
    OrderStatusUpdateForm,
    OrderUpdateForm,
    ShippingFeeEstimatorForm,
)
from mangementlogistics.orders.models import (
    CODReconciliation,
    DeliveryTrip,
    Order,
    OrderReturn,
)
from mangementlogistics.orders.selectors import (
    cod_reconciliation_get_by_id,
    cod_reconciliation_get_eligible_orders,
    cod_reconciliation_get_summary_stats,
    cod_reconciliation_list,
    delivery_trip_get_by_id,
    delivery_trip_get_eligible_orders,
    delivery_trip_get_summary_stats,
    delivery_trip_list,
    order_get_by_id,
    order_get_by_tracking_number,
    order_get_tracking_history,
    order_list,
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


@login_required
def cod_reconciliation_list_view(request):
    """
    Renders list of COD reconciliation statements with status filtering and financial summary KPIs.
    """
    status_filter = request.GET.get("status") or None
    reconciliations = cod_reconciliation_list(
        user=request.user,
        status=status_filter,
    )
    summary_stats = cod_reconciliation_get_summary_stats(user=request.user)
    is_admin = request.user.is_superuser or getattr(request.user, "role", None) == UserRole.ADMIN

    return render(
        request,
        "orders/reconciliation_list.html",
        {
            "reconciliations": reconciliations,
            "selected_status": status_filter,
            "summary_stats": summary_stats,
            "is_admin": is_admin,
            "status_choices": CODReconciliationStatus.choices,
        },
    )


@login_required
def cod_reconciliation_detail_view(request, reconciliation_id: int):
    """
    Renders detailed statement breakdown including orders, financial totals, and processing actions.
    """
    reconciliation = cod_reconciliation_get_by_id(
        reconciliation_id=reconciliation_id,
        user=request.user,
    )
    if not reconciliation:
        messages.error(request, "Không tìm thấy bảng kê đối soát hoặc bạn không có quyền truy cập.")
        return redirect("orders:reconciliation-list")

    is_admin = request.user.is_superuser or getattr(request.user, "role", None) == UserRole.ADMIN
    process_form = CODReconciliationProcessForm() if is_admin else None
    orders = reconciliation.orders.all().order_by("-delivered_at", "-created_at")

    return render(
        request,
        "orders/reconciliation_detail.html",
        {
            "reconciliation": reconciliation,
            "orders": orders,
            "is_admin": is_admin,
            "process_form": process_form,
        },
    )


@login_required
def cod_reconciliation_generate_view(request):
    """
    Processes creation of a new COD reconciliation statement for delivered orders.
    """
    is_admin = request.user.is_superuser or getattr(request.user, "role", None) == UserRole.ADMIN

    if request.method == "POST":
        form = CODReconciliationGenerateForm(request.POST, user=request.user)
        if form.is_valid():
            target_customer = form.cleaned_data.get("customer") if is_admin else request.user
            notes = form.cleaned_data.get("notes", "")

            try:
                rec = cod_reconciliation_generate(
                    customer=target_customer,
                    actor=request.user,
                    notes=notes,
                )
                messages.success(
                    request,
                    f"Tạo kỳ đối soát {rec.code} thành công với {rec.total_orders_count} đơn hàng! Số tiền quyết toán: {rec.net_payout_amount:,.0f} đ",
                )
                return redirect("orders:reconciliation-detail", reconciliation_id=rec.id)
            except (CODReconciliationError, OrderPermissionDeniedError) as exc:
                messages.error(request, str(exc))
    else:
        form = CODReconciliationGenerateForm(user=request.user)

    target_customer = request.user
    eligible_orders = cod_reconciliation_get_eligible_orders(customer=target_customer)

    return render(
        request,
        "orders/reconciliation_form.html",
        {
            "form": form,
            "is_admin": is_admin,
            "eligible_orders": eligible_orders,
        },
    )


@login_required
def cod_reconciliation_process_view(request, reconciliation_id: int):
    """
    Processes administrator confirmation or payment transition on a reconciliation statement.
    """
    if request.method != "POST":
        return redirect("orders:reconciliation-detail", reconciliation_id=reconciliation_id)

    reconciliation = cod_reconciliation_get_by_id(
        reconciliation_id=reconciliation_id,
        user=request.user,
    )
    if not reconciliation:
        messages.error(request, "Không tìm thấy bảng kê đối soát.")
        return redirect("orders:reconciliation-list")

    form = CODReconciliationProcessForm(request.POST)
    if form.is_valid():
        action = form.cleaned_data["action"]
        notes = form.cleaned_data.get("notes", "")

        try:
            if action == "CONFIRM":
                cod_reconciliation_confirm(
                    reconciliation=reconciliation,
                    actor=request.user,
                    notes=notes,
                )
                messages.success(request, f"Đã xác nhận bảng kê đối soát {reconciliation.code} thành công!")
            elif action == "MARK_PAID":
                cod_reconciliation_mark_paid(
                    reconciliation=reconciliation,
                    actor=request.user,
                    notes=notes,
                )
                messages.success(request, f"Đã chuyển trạng thái bảng kê {reconciliation.code} sang Đã quyết toán thành công!")
        except (CODReconciliationError, OrderPermissionDeniedError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Dữ liệu xử lý không hợp lệ.")

    return redirect("orders:reconciliation-detail", reconciliation_id=reconciliation.id)


@login_required
def cod_reconciliation_export_csv_view(request, reconciliation_id: int):
    """
    Exports all items in a COD reconciliation statement to a formatted CSV file.
    """
    reconciliation = cod_reconciliation_get_by_id(
        reconciliation_id=reconciliation_id,
        user=request.user,
    )
    if not reconciliation:
        messages.error(request, "Không tìm thấy bảng kê đối soát.")
        return redirect("orders:reconciliation-list")

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="bang-ke-doi-soat-{reconciliation.code}.csv"'

    # Write UTF-8 BOM for Microsoft Excel compatibility
    response.write("\ufeff")

    writer = csv.writer(response)
    writer.writerow(["BẢNG KÊ ĐỐI SOÁT & QUYẾT TOÁN TIỀN THU HỘ COD"])
    writer.writerow(["Mã bảng kê", reconciliation.code])
    writer.writerow(["Khách hàng", reconciliation.customer.name or reconciliation.customer.email])
    writer.writerow(["Email", reconciliation.customer.email])
    writer.writerow(["Trạng thái", reconciliation.get_status_display()])
    writer.writerow(["Ngày tạo", reconciliation.created_at.strftime("%d/%m/%Y %H:%M")])
    writer.writerow([])

    writer.writerow([
        "STT",
        "Mã vận đơn",
        "Tên người nhận",
        "Số điện thoại",
        "Địa chỉ nhận hàng",
        "Ngày giao thành công",
        "Tiền thu hộ COD (VNĐ)",
        "Cước phí vận chuyển (VNĐ)",
        "Số tiền thực nhận (VNĐ)",
        "Trạng thái thanh toán",
    ])

    orders = reconciliation.orders.all().order_by("-delivered_at", "-created_at")
    for idx, order in enumerate(orders, start=1):
        delivered_str = order.delivered_at.strftime("%d/%m/%Y %H:%M") if order.delivered_at else "-"
        net_order = order.cod_amount - order.shipping_fee
        writer.writerow([
            idx,
            order.tracking_number,
            order.receiver_name,
            order.receiver_phone,
            order.receiver_address,
            delivered_str,
            int(order.cod_amount),
            int(order.shipping_fee),
            int(net_order),
            order.get_payment_status_display(),
        ])

    writer.writerow([])
    writer.writerow([
        "TỔNG CỘNG",
        f"{reconciliation.total_orders_count} đơn hàng",
        "",
        "",
        "",
        "",
        int(reconciliation.total_cod_amount),
        int(reconciliation.total_shipping_fees),
        int(reconciliation.net_payout_amount),
        reconciliation.get_status_display(),
    ])

    return response


@login_required
def order_return_list_view(request):
    """
    Renders the reverse logistics list of return requests with status filtering, search and KPI stats.
    """
    status_filter = request.GET.get("status") or None
    search_query = request.GET.get("search") or None

    returns = order_return_list(
        user=request.user,
        status=status_filter,
        search=search_query,
    )
    summary_stats = order_return_get_summary_stats(user=request.user)
    is_admin = request.user.is_superuser or getattr(request.user, "role", None) == UserRole.ADMIN
    is_driver = getattr(request.user, "role", None) == UserRole.DRIVER

    return render(
        request,
        "orders/return_list.html",
        {
            "returns": returns,
            "selected_status": status_filter,
            "search_query": search_query or "",
            "summary_stats": summary_stats,
            "is_admin": is_admin,
            "is_driver": is_driver,
            "status_choices": ReturnStatus.choices,
        },
    )


@login_required
def order_return_detail_view(request, return_id: int):
    """
    Renders full details of an order return request including tracking timeline and action form.
    """
    order_return = order_return_get_by_id(return_id=return_id, user=request.user)
    if not order_return:
        messages.error(request, "Không tìm thấy yêu cầu hoàn trả hoặc bạn không có quyền truy cập.")
        return redirect("orders:return-list")

    is_admin = request.user.is_superuser or getattr(request.user, "role", None) == UserRole.ADMIN
    is_driver = getattr(request.user, "role", None) == UserRole.DRIVER and order_return.assigned_driver_id == request.user.id

    action_form = None
    if is_admin or is_driver:
        action_form = OrderReturnActionForm(
            initial={
                "status": order_return.status,
                "driver": order_return.assigned_driver,
            }
        )

    return render(
        request,
        "orders/return_detail.html",
        {
            "return_obj": order_return,
            "order_return": order_return,
            "order": order_return.order,
            "is_admin": is_admin,
            "is_driver": is_driver,
            "action_form": action_form,
        },
    )


@login_required
def order_return_create_view(request, order_id: int):
    """
    Renders and processes the form to create a reverse logistics return request for a specific order.
    """
    order = order_get_by_id(order_id=order_id, user=request.user)
    if not order:
        messages.error(request, "Không tìm thấy đơn hàng để yêu cầu hoàn trả.")
        return redirect("orders:order-list")

    if request.method == "POST":
        form = OrderReturnCreateForm(request.POST)
        if form.is_valid():
            try:
                order_return = order_return_create(
                    order=order,
                    actor=request.user,
                    **form.cleaned_data,
                )
                messages.success(
                    request,
                    f"Tạo yêu cầu hoàn trả {order_return.return_code} thành công! Hệ thống đang tiếp nhận xử lý.",
                )
                return redirect("orders:return-detail", return_id=order_return.id)
            except (OrderReturnError, OrderPermissionDeniedError) as exc:
                messages.error(request, str(exc))
    else:
        # Initial defaults from the master order
        initial_data = {
            "return_address": order.sender_address,
            "pickup_address": order.receiver_address,
            "return_shipping_fee": order.shipping_fee,
            "refund_amount": order.cod_amount if order.status == OrderStatus.DELIVERED else 0,
            "fee_payer": ReturnFeePayer.SHOP,
        }
        form = OrderReturnCreateForm(initial=initial_data)

    return render(
        request,
        "orders/return_form.html",
        {
            "form": form,
            "order": order,
        },
    )


@login_required
def order_return_action_view(request, return_id: int):
    """
    Processes administrative or driver actions on an order return (approve, reject, update status).
    """
    if request.method != "POST":
        return redirect("orders:return-detail", return_id=return_id)

    order_return = order_return_get_by_id(return_id=return_id, user=request.user)
    if not order_return:
        messages.error(request, "Không tìm thấy yêu cầu hoàn trả.")
        return redirect("orders:return-list")

    form = OrderReturnActionForm(request.POST)
    if form.is_valid():
        action = form.cleaned_data["action"]
        notes = form.cleaned_data.get("notes", "")
        driver = form.cleaned_data.get("driver")
        location = form.cleaned_data.get("location", "")
        new_status = form.cleaned_data.get("status")

        try:
            if action == "APPROVE":
                order_return_approve(
                    order_return=order_return,
                    actor=request.user,
                    driver_id=driver.id if driver else None,
                    notes=notes,
                )
                messages.success(request, f"Đã duyệt yêu cầu hoàn trả {order_return.return_code} thành công!")
            elif action == "REJECT":
                order_return_reject(
                    order_return=order_return,
                    actor=request.user,
                    reason=notes,
                )
                messages.success(request, f"Đã từ chối yêu cầu hoàn trả {order_return.return_code}!")
            elif action == "UPDATE_STATUS":
                if not new_status:
                    messages.error(request, "Vui lòng chọn trạng thái mới cần cập nhật.")
                    return redirect("orders:return-detail", return_id=return_id)
                order_return_update_status(
                    order_return=order_return,
                    new_status=new_status,
                    actor=request.user,
                    location=location,
                    note=notes,
                )
                messages.success(request, f"Cập nhật tiến trình trả hàng thành công sang: {order_return.get_status_display()}!")
        except (OrderReturnError, OrderPermissionDeniedError, DriverAssignmentError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Dữ liệu xử lý không hợp lệ.")

    return redirect("orders:return-detail", return_id=return_id)


@login_required
def order_return_print_view(request, return_id: int):
    """
    Renders printable RMA return slip (Reverse Logistics Air Waybill).
    """
    order_return = order_return_get_by_id(return_id=return_id, user=request.user)
    if not order_return:
        messages.error(request, "Không tìm thấy yêu cầu hoàn trả để in phiếu.")
        return redirect("orders:return-list")

    return render(
        request,
        "orders/return_print.html",
        {
            "order_return": order_return,
            "order": order_return.order,
        },
    )


# ==============================================================================
# Delivery Trip & Route Dispatch Views
# ==============================================================================

@login_required
def delivery_trip_list_view(request):
    """
    Renders the delivery trip runs list and KPI statistics scoped to user role.
    """
    status_filter = request.GET.get("status")
    search_query = request.GET.get("q")

    trips = delivery_trip_list(
        user=request.user,
        status=status_filter,
        search=search_query,
    )
    summary_stats = delivery_trip_get_summary_stats(user=request.user)

    is_admin = request.user.is_superuser or getattr(request.user, "role", None) == UserRole.ADMIN
    is_driver = getattr(request.user, "role", None) == UserRole.DRIVER

    return render(
        request,
        "orders/trips/trip_list.html",
        {
            "trips": trips,
            "selected_status": status_filter,
            "search_query": search_query or "",
            "summary_stats": summary_stats,
            "is_admin": is_admin,
            "is_driver": is_driver,
            "status_choices": TripStatus.choices,
        },
    )


@login_required
def delivery_trip_detail_view(request, trip_id: int):
    """
    Renders details of a delivery trip manifest with its assigned parcels and operational controls.
    """
    trip = delivery_trip_get_by_id(trip_id=trip_id, user=request.user)
    if not trip:
        messages.error(request, "Không tìm thấy chuyến giao hàng hoặc bạn không có quyền truy cập.")
        return redirect("orders:trip-list")

    is_admin = request.user.is_superuser or getattr(request.user, "role", None) == UserRole.ADMIN
    is_driver = getattr(request.user, "role", None) == UserRole.DRIVER and trip.driver_id == request.user.id

    action_form = DeliveryTripActionForm() if (is_admin or is_driver) else None

    return render(
        request,
        "orders/trips/trip_detail.html",
        {
            "trip": trip,
            "orders": trip.trip_orders.all(),
            "is_admin": is_admin,
            "is_driver": is_driver,
            "action_form": action_form,
        },
    )


@login_required
def delivery_trip_create_view(request):
    """
    Allows dispatch supervisor or driver to initialize a new delivery run.
    """
    is_admin = request.user.is_superuser or getattr(request.user, "role", None) == UserRole.ADMIN
    is_driver = getattr(request.user, "role", None) == UserRole.DRIVER

    if not (is_admin or is_driver):
        messages.error(request, "Bạn không có quyền lập chuyến xe giao hàng.")
        return redirect("orders:order-list")

    if request.method == "POST":
        form = DeliveryTripCreateForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                trip = delivery_trip_create(
                    driver=form.cleaned_data["driver"],
                    actor=request.user,
                    route_name=form.cleaned_data["route_name"],
                    departure_hub=form.cleaned_data["departure_hub"],
                    vehicle_type=form.cleaned_data["vehicle_type"],
                    license_plate=form.cleaned_data.get("license_plate", ""),
                    notes=form.cleaned_data.get("notes", ""),
                )
                messages.success(request, f"Tạo chuyến xe {trip.trip_code} thành công! Hãy gom đơn hàng vào chuyến.")
                return redirect("orders:trip-add-orders", trip_id=trip.id)
            except (DeliveryTripError, OrderPermissionDeniedError) as exc:
                messages.error(request, str(exc))
    else:
        form = DeliveryTripCreateForm(user=request.user)

    return render(
        request,
        "orders/trips/trip_form.html",
        {
            "form": form,
        },
    )


@login_required
def delivery_trip_add_orders_view(request, trip_id: int):
    """
    Renders eligible parcels picker to batch add orders into a trip.
    """
    trip = delivery_trip_get_by_id(trip_id=trip_id, user=request.user)
    if not trip:
        messages.error(request, "Không tìm thấy chuyến xe giao hàng.")
        return redirect("orders:trip-list")

    is_admin = request.user.is_superuser or getattr(request.user, "role", None) == UserRole.ADMIN
    is_driver = getattr(request.user, "role", None) == UserRole.DRIVER and trip.driver_id == request.user.id
    if not (is_admin or is_driver):
        messages.error(request, "Bạn không có quyền phân bổ đơn hàng vào chuyến xe này.")
        return redirect("orders:trip-detail", trip_id=trip.id)

    if request.method == "POST":
        form = DeliveryTripAddOrdersForm(request.POST, trip=trip)
        if form.is_valid():
            selected_orders = form.cleaned_data["orders"]
            try:
                order_ids = [o.id for o in selected_orders]
                updated = delivery_trip_add_orders(trip=trip, order_ids=order_ids, actor=request.user)
                messages.success(request, f"Đã gom thành công {len(updated)} đơn hàng vào chuyến xe {trip.trip_code}!")
                return redirect("orders:trip-detail", trip_id=trip.id)
            except (DeliveryTripError, OrderPermissionDeniedError) as exc:
                messages.error(request, str(exc))
    else:
        form = DeliveryTripAddOrdersForm(trip=trip)

    return render(
        request,
        "orders/trips/trip_add_orders.html",
        {
            "trip": trip,
            "form": form,
        },
    )


@login_required
def delivery_trip_action_view(request, trip_id: int):
    """
    Processes dispatch, completion, cancellation, and parcel removal actions for a trip.
    """
    if request.method != "POST":
        return redirect("orders:trip-detail", trip_id=trip_id)

    trip = delivery_trip_get_by_id(trip_id=trip_id, user=request.user)
    if not trip:
        messages.error(request, "Không tìm thấy chuyến giao hàng.")
        return redirect("orders:trip-list")

    form = DeliveryTripActionForm(request.POST)
    if form.is_valid():
        action = form.cleaned_data["action"]
        notes = form.cleaned_data.get("notes", "")
        order_id = form.cleaned_data.get("order_id")

        try:
            if action == "DISPATCH":
                delivery_trip_dispatch(trip=trip, actor=request.user, notes=notes)
                messages.success(request, f"Chuyến xe {trip.trip_code} đã xuất bến thành công! Tất cả bưu phẩm đã chuyển sang Đang vận chuyển.")
            elif action == "COMPLETE":
                delivery_trip_complete(trip=trip, actor=request.user, notes=notes)
                messages.success(request, f"Chuyến xe {trip.trip_code} đã hoàn thành toàn bộ lộ trình!")
            elif action == "CANCEL":
                delivery_trip_cancel(trip=trip, actor=request.user, reason=notes)
                messages.success(request, f"Đã hủy chuyến xe {trip.trip_code} thành công.")
            elif action == "REMOVE_ORDER":
                if not order_id:
                    messages.error(request, "Không xác định được đơn hàng cần gỡ.")
                else:
                    delivery_trip_remove_order(trip=trip, order_id=order_id, actor=request.user)
                    messages.success(request, "Đã gỡ đơn hàng khỏi chuyến xe.")
        except (DeliveryTripError, OrderPermissionDeniedError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Dữ liệu thao tác không hợp lệ.")

    return redirect("orders:trip-detail", trip_id=trip.id)


@login_required
def delivery_trip_print_view(request, trip_id: int):
    """
    Renders printable delivery run sheet / trip manifest (A4 / Letter).
    """
    trip = delivery_trip_get_by_id(trip_id=trip_id, user=request.user)
    if not trip:
        messages.error(request, "Không tìm thấy chuyến giao hàng để in bảng kê.")
        return redirect("orders:trip-list")

    return render(
        request,
        "orders/trips/trip_manifest_print.html",
        {
            "trip": trip,
            "orders": trip.trip_orders.all(),
        },
    )







