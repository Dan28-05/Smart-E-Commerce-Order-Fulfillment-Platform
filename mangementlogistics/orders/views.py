# mangementlogistics/orders/views.py
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from mangementlogistics.orders.exceptions import (
    DriverAssignmentError,
    InvalidOrderStatusError,
    OrderPermissionDeniedError,
)
from mangementlogistics.orders.forms import (
    OrderCancelForm,
    OrderCreateForm,
    OrderStatusUpdateForm,
    OrderUpdateForm,
)
from mangementlogistics.orders.models import Order
from mangementlogistics.orders.selectors import (
    order_get_by_id,
    order_get_by_tracking_number,
    order_list,
)
from mangementlogistics.orders.services import (
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
        # Pre-fill sender details from customer profile if available
        initial_data = {
            "sender_name": request.user.name or "",
            "sender_phone": request.user.phone_number or "",
            "sender_address": request.user.address or "",
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

    status_form = None
    if is_admin or is_driver:
        status_form = OrderStatusUpdateForm(
            initial={
                "status": order.status,
                "driver": order.driver,
            }
        )

    return render(
        request,
        "orders/order_detail.html",
        {
            "order": order,
            "is_admin": is_admin,
            "is_driver": is_driver,
            "status_form": status_form,
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
        driver = form.cleaned_data.get("driver")
        driver_id = driver.id if driver else None

        try:
            order_update_status(
                order=order,
                new_status=new_status,
                actor=request.user,
                driver_id=driver_id,
            )
            messages.success(request, f"Cập nhật trạng thái sang '{order.get_status_display()}' thành công!")
        except (InvalidOrderStatusError, OrderPermissionDeniedError, DriverAssignmentError) as exc:
            messages.error(request, str(exc))

    return redirect("orders:order-detail", order_id=order.id)


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
    Public tracking view: user inputs tracking number to check progress.
    """
    tracking_number = request.GET.get("tracking") or ""
    order = None
    not_found = False

    if tracking_number:
        order = order_get_by_tracking_number(tracking_number=tracking_number)
        if not order:
            not_found = True

    return render(
        request,
        "orders/order_track.html",
        {
            "tracking_number": tracking_number,
            "order": order,
            "not_found": not_found,
        },
    )
