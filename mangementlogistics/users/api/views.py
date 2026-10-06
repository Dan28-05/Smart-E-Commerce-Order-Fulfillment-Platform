# mangementlogistics/users/api/views.py
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from mangementlogistics.users.api.serializers import (
    UserCreateInputSerializer,
    UserOutputSerializer,
    UserUpdateInputSerializer,
)
from mangementlogistics.users.exceptions import DuplicateEmailError, UserNotFoundError
from mangementlogistics.users.selectors import user_get_by_id, user_list
from mangementlogistics.users.services import user_create, user_delete, user_update


class UserListCreateApi(APIView):
    """
    List all users or create a new user.
    """

    @extend_schema(
        summary="Lấy danh sách người dùng",
        responses={200: UserOutputSerializer(many=True)},
    )
    def get(self, request):
        users = user_list()
        data = UserOutputSerializer(users, many=True).data
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Tạo mới người dùng",
        request=UserCreateInputSerializer,
        responses={201: UserOutputSerializer},
    )
    def post(self, request):
        serializer = UserCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = user_create(**serializer.validated_data)
        except DuplicateEmailError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        data = UserOutputSerializer(user).data
        return Response(data, status=status.HTTP_201_CREATED)


class UserDetailApi(APIView):
    """
    Retrieve, update or deactivate a specific user.
    """

    @extend_schema(
        summary="Xem chi tiết người dùng",
        responses={200: UserOutputSerializer},
    )
    def get(self, request, user_id: int):
        user = user_get_by_id(user_id=user_id)
        if not user:
            return Response({"error": "Người dùng không tồn tại"}, status=status.HTTP_404_NOT_FOUND)

        data = UserOutputSerializer(user).data
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Cập nhật thông tin người dùng",
        request=UserUpdateInputSerializer,
        responses={200: UserOutputSerializer},
    )
    def patch(self, request, user_id: int):
        user = user_get_by_id(user_id=user_id)
        if not user:
            return Response({"error": "Người dùng không tồn tại"}, status=status.HTTP_404_NOT_FOUND)

        serializer = UserUpdateInputSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            updated_user = user_update(user=user, **serializer.validated_data)
        except DuplicateEmailError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        data = UserOutputSerializer(updated_user).data
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Vô hiệu hóa (xóa mềm) người dùng",
        responses={204: None},
    )
    def delete(self, request, user_id: int):
        user = user_get_by_id(user_id=user_id)
        if not user:
            return Response({"error": "Người dùng không tồn tại"}, status=status.HTTP_404_NOT_FOUND)

        user_delete(user=user)
        return Response(status=status.HTTP_204_NO_CONTENT)
