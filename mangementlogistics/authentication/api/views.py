# mangementlogistics/authentication/api/views.py
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from mangementlogistics.authentication.api.serializers import (
    LoginInputSerializer,
    LoginOutputSerializer,
    LogoutInputSerializer,
    TokenRefreshInputSerializer,
    TokenRefreshOutputSerializer,
    TokenVerifyInputSerializer,
)
from mangementlogistics.authentication.exceptions import (
    InactiveAccountError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from mangementlogistics.authentication.services import (
    auth_blacklist_token,
    auth_login_with_credentials,
    auth_refresh_access_token,
    auth_verify_token,
)


class LoginApi(APIView):
    """
    Authenticate user by email and password, returning JWT access & refresh tokens.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Đăng nhập tài khoản bằng JWT (Email & Mật khẩu)",
        request=LoginInputSerializer,
        responses={
            200: LoginOutputSerializer,
            400: {"type": "object", "properties": {"error": {"type": "string"}}},
            401: {"type": "object", "properties": {"error": {"type": "string"}}},
        },
    )
    def post(self, request):
        serializer = LoginInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        try:
            user, tokens = auth_login_with_credentials(email=email, password=password)
        except InvalidCredentialsError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        except InactiveAccountError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        response_data = {
            "access": tokens["access"],
            "refresh": tokens["refresh"],
            "user": user,
        }
        output_serializer = LoginOutputSerializer(response_data)
        return Response(output_serializer.data, status=status.HTTP_200_OK)


class TokenRefreshApi(APIView):
    """
    Obtain a new JWT access token using a valid refresh token.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Lấy access token mới từ refresh token",
        request=TokenRefreshInputSerializer,
        responses={
            200: TokenRefreshOutputSerializer,
            400: {"type": "object", "properties": {"error": {"type": "string"}}},
        },
    )
    def post(self, request):
        serializer = TokenRefreshInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data["refresh"]

        try:
            new_access_token = auth_refresh_access_token(refresh_token=refresh_token)
        except InvalidTokenError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        output_serializer = TokenRefreshOutputSerializer({"access": new_access_token})
        return Response(output_serializer.data, status=status.HTTP_200_OK)


class TokenVerifyApi(APIView):
    """
    Verify whether a given JWT token is cryptographically valid.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Kiểm tra tính hợp lệ của JWT token",
        request=TokenVerifyInputSerializer,
        responses={
            200: {"type": "object", "properties": {"valid": {"type": "boolean"}}},
            400: {"type": "object", "properties": {"error": {"type": "string"}}},
        },
    )
    def post(self, request):
        serializer = TokenVerifyInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data["token"]

        try:
            auth_verify_token(token=token)
        except InvalidTokenError as exc:
            return Response({"error": str(exc), "valid": False}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"valid": True}, status=status.HTTP_200_OK)


class LogoutApi(APIView):
    """
    Revoke or invalidate user session and refresh token.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Đăng xuất (thu hồi refresh token)",
        request=LogoutInputSerializer,
        responses={
            200: {"type": "object", "properties": {"message": {"type": "string"}}},
        },
    )
    def post(self, request):
        serializer = LogoutInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data.get("refresh")
        if refresh_token:
            try:
                auth_blacklist_token(refresh_token=refresh_token)
            except InvalidTokenError:
                pass

        return Response({"message": "Đăng xuất thành công."}, status=status.HTTP_200_OK)
