# mangementlogistics/orders/api/views.py
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from mangementlogistics.orders.api.serializers import (
    OrderCancelInputSerializer,
    OrderCheckpointInputSerializer,
    OrderCreateInputSerializer,
    OrderOutputSerializer,
    OrderStatusUpdateInputSerializer,
    OrderTrackingHistorySerializer,
    OrderUpdateInputSerializer,
)
from mangementlogistics.orders.exceptions import (
    DriverAssignmentError,
    InvalidOrderStatusError,
    OrderPermissionDeniedError,
)
from mangementlogistics.orders.selectors import (
    order_get_by_id,
    order_get_by_tracking_number,
    order_list,
)
from mangementlogistics.orders.services import (
    order_add_checkpoint,
    order_cancel,
    order_create,
    order_delete,
    order_update,
    order_update_status,
)
from mangementlogistics.users.constants import UserRole
from mangementlogistics.users.models import User


class OrderListCreateApi(APIView):
    """
    List orders or create a new delivery order.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Lấy danh sách đơn hàng (theo quyền: Khách hàng, Tài xế, Quản trị viên)",
        parameters=[
            OpenApiParameter(name="status", description="Lọc theo trạng thái đơn hàng", required=False, type=str),
            OpenApiParameter(name="search", description="Tìm kiếm theo mã vận đơn, người gửi, người nhận", required=False, type=str),
        ],
        responses={200: OrderOutputSerializer(many=True)},
    )
    def get(self, request):
        status_filter = request.GET.get("status") or None
        search_query = request.GET.get("search") or None

        orders = order_list(
            user=request.user,
            status=status_filter,
            search=search_query,
        )
        data = OrderOutputSerializer(orders, many=True).data
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Tạo mới đơn vận chuyển hàng hóa",
        request=OrderCreateInputSerializer,
        responses={201: OrderOutputSerializer, 400: {"type": "object", "properties": {"error": {"type": "string"}}}},
    )
    def post(self, request):
        serializer = OrderCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        is_admin = request.user.is_superuser or getattr(request.user, "role", None) == UserRole.ADMIN

        # Xác định khách hàng tạo đơn
        customer = request.user
        customer_id = validated_data.pop("customer_id", None)
        if is_admin and customer_id:
            specified_customer = User.objects.filter(id=customer_id).first()
            if not specified_customer:
                return Response({"error": "Khách hàng được chỉ định không tồn tại."}, status=status.HTTP_400_BAD_REQUEST)
            customer = specified_customer

        # Xác định tài xế (nếu có)
        driver = None
        driver_id = validated_data.pop("driver_id", None)
        if driver_id:
            driver = User.objects.filter(id=driver_id, role=UserRole.DRIVER).first()
            if not driver:
                return Response({"error": "Tài xế được chỉ định không tồn tại hoặc không hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = order_create(
                customer=customer,
                driver=driver,
                **validated_data,
            )
        except DriverAssignmentError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        data = OrderOutputSerializer(order).data
        return Response(data, status=status.HTTP_201_CREATED)


class OrderDetailApi(APIView):
    """
    Retrieve, update or delete a specific order.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Xem chi tiết đơn hàng",
        responses={200: OrderOutputSerializer, 404: {"type": "object", "properties": {"error": {"type": "string"}}}},
    )
    def get(self, request, order_id: int):
        order = order_get_by_id(order_id=order_id, user=request.user)
        if not order:
            return Response({"error": "Đơn hàng không tồn tại hoặc bạn không có quyền xem."}, status=status.HTTP_404_NOT_FOUND)

        data = OrderOutputSerializer(order).data
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Cập nhật thông tin đơn hàng",
        request=OrderUpdateInputSerializer,
        responses={200: OrderOutputSerializer, 400: {"type": "object", "properties": {"error": {"type": "string"}}}},
    )
    def patch(self, request, order_id: int):
        order = order_get_by_id(order_id=order_id, user=request.user)
        if not order:
            return Response({"error": "Đơn hàng không tồn tại hoặc bạn không có quyền chỉnh sửa."}, status=status.HTTP_404_NOT_FOUND)

        serializer = OrderUpdateInputSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            updated_order = order_update(order=order, actor=request.user, **serializer.validated_data)
        except (OrderPermissionDeniedError, DriverAssignmentError) as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        data = OrderOutputSerializer(updated_order).data
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Xóa đơn hàng (Quản trị viên hoặc Khách hàng khi đơn chưa tiếp nhận)",
        responses={204: None, 400: {"type": "object", "properties": {"error": {"type": "string"}}}},
    )
    def delete(self, request, order_id: int):
        order = order_get_by_id(order_id=order_id, user=request.user)
        if not order:
            return Response({"error": "Đơn hàng không tồn tại."}, status=status.HTTP_404_NOT_FOUND)

        try:
            order_delete(order=order, actor=request.user)
        except OrderPermissionDeniedError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)


class OrderStatusUpdateApi(APIView):
    """
    Update the delivery status of an order.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Cập nhật trạng thái giao nhận đơn hàng",
        request=OrderStatusUpdateInputSerializer,
        responses={200: OrderOutputSerializer, 400: {"type": "object", "properties": {"error": {"type": "string"}}}},
    )
    def post(self, request, order_id: int):
        order = order_get_by_id(order_id=order_id, user=request.user)
        if not order:
            return Response({"error": "Đơn hàng không tồn tại."}, status=status.HTTP_404_NOT_FOUND)

        serializer = OrderStatusUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data["status"]
        driver_id = serializer.validated_data.get("driver_id")
        location = serializer.validated_data.get("location", "")
        note = serializer.validated_data.get("note", "")

        try:
            updated_order = order_update_status(
                order=order,
                new_status=new_status,
                actor=request.user,
                driver_id=driver_id,
                location=location,
                note=note,
            )
        except (InvalidOrderStatusError, OrderPermissionDeniedError, DriverAssignmentError) as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        data = OrderOutputSerializer(updated_order).data
        return Response(data, status=status.HTTP_200_OK)


class OrderCheckpointApi(APIView):
    """
    Record a new transit checkpoint/milestone along the route.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Ghi nhận mốc hành trình / checkpoint cho đơn hàng",
        request=OrderCheckpointInputSerializer,
        responses={201: OrderTrackingHistorySerializer, 400: {"type": "object", "properties": {"error": {"type": "string"}}}},
    )
    def post(self, request, order_id: int):
        order = order_get_by_id(order_id=order_id, user=request.user)
        if not order:
            return Response({"error": "Đơn hàng không tồn tại."}, status=status.HTTP_404_NOT_FOUND)

        serializer = OrderCheckpointInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        location = serializer.validated_data["location"]
        note = serializer.validated_data["note"]

        try:
            event = order_add_checkpoint(
                order=order,
                location=location,
                note=note,
                actor=request.user,
            )
        except OrderPermissionDeniedError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        data = OrderTrackingHistorySerializer(event).data
        return Response(data, status=status.HTTP_201_CREATED)



class OrderCancelApi(APIView):
    """
    Cancel an order before it enters transit.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Hủy đơn hàng",
        request=OrderCancelInputSerializer,
        responses={200: OrderOutputSerializer, 400: {"type": "object", "properties": {"error": {"type": "string"}}}},
    )
    def post(self, request, order_id: int):
        order = order_get_by_id(order_id=order_id, user=request.user)
        if not order:
            return Response({"error": "Đơn hàng không tồn tại."}, status=status.HTTP_404_NOT_FOUND)

        serializer = OrderCancelInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("reason", "")

        try:
            cancelled_order = order_cancel(order=order, actor=request.user, reason=reason)
        except (InvalidOrderStatusError, OrderPermissionDeniedError) as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        data = OrderOutputSerializer(cancelled_order).data
        return Response(data, status=status.HTTP_200_OK)


class OrderTrackPublicApi(APIView):
    """
    Public tracking endpoint accessible without login.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Tra cứu hành trình đơn hàng công khai bằng mã vận đơn",
        responses={200: OrderOutputSerializer, 404: {"type": "object", "properties": {"error": {"type": "string"}}}},
    )
    def get(self, request, tracking_number: str):
        order = order_get_by_tracking_number(tracking_number=tracking_number)
        if not order:
            return Response({"error": f"Không tìm thấy đơn hàng với mã vận đơn '{tracking_number}'."}, status=status.HTTP_404_NOT_FOUND)

        data = OrderOutputSerializer(order).data
        return Response(data, status=status.HTTP_200_OK)
