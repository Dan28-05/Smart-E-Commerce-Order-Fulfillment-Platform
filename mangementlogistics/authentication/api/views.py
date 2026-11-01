# mangementlogistics/authentication/api/views.py
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from mangementlogistics.authentication.api.serializers import (
    ChangePasswordInputSerializer,
    LoginInputSerializer,
    LoginOutputSerializer,
    LogoutInputSerializer,
    PasswordResetConfirmInputSerializer,
    PasswordResetRequestInputSerializer,
    PasswordResetValidateTokenInputSerializer,
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
    auth_change_password,
    auth_login_with_credentials,
    auth_password_reset_confirm,
    auth_password_reset_request,
    auth_password_reset_validate_token,
    auth_refresh_access_token,
    auth_verify_token,
)
from mangementlogistics.users.exceptions import InvalidPasswordError


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


class ChangePasswordApi(APIView):
    """
    Change password for the currently authenticated user.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Đổi mật khẩu người dùng hiện tại",
        request=ChangePasswordInputSerializer,
        responses={
            200: {"type": "object", "properties": {"message": {"type": "string"}}},
            400: {"type": "object", "properties": {"error": {"type": "string"}}},
        },
    )
    def post(self, request):
        serializer = ChangePasswordInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            auth_change_password(
                user=request.user,
                old_password=serializer.validated_data["old_password"],
                new_password=serializer.validated_data["new_password"],
                new_password_confirm=serializer.validated_data["new_password_confirm"],
            )
        except InvalidPasswordError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": "Đổi mật khẩu thành công!"}, status=status.HTTP_200_OK)


class PasswordResetRequestApi(APIView):
    """
    Request password reset email.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Yêu cầu đặt lại mật khẩu qua email",
        request=PasswordResetRequestInputSerializer,
        responses={
            200: {"type": "object", "properties": {"message": {"type": "string"}}},
            400: {"type": "object", "properties": {"error": {"type": "string"}}},
        },
    )
    def post(self, request):
        serializer = PasswordResetRequestInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        base_url = request.build_absolute_uri("/")

        _, message = auth_password_reset_request(email=email, base_url=base_url)
        return Response({"message": message}, status=status.HTTP_200_OK)


class PasswordResetValidateTokenApi(APIView):
    """
    Validate if password reset token and uid are valid.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Kiểm tra token đặt lại mật khẩu có hợp lệ hay không",
        request=PasswordResetValidateTokenInputSerializer,
        responses={
            200: {"type": "object", "properties": {"valid": {"type": "boolean"}}},
            400: {"type": "object", "properties": {"error": {"type": "string"}}},
        },
    )
    def post(self, request):
        serializer = PasswordResetValidateTokenInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uidb64 = serializer.validated_data["uidb64"]
        token = serializer.validated_data["token"]

        try:
            auth_password_reset_validate_token(uidb64=uidb64, token=token)
        except InvalidTokenError as exc:
            return Response({"error": str(exc), "valid": False}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"valid": True}, status=status.HTTP_200_OK)


class PasswordResetConfirmApi(APIView):
    """
    Confirm password reset with new password.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Xác nhận đặt lại mật khẩu mới",
        request=PasswordResetConfirmInputSerializer,
        responses={
            200: {"type": "object", "properties": {"message": {"type": "string"}}},
            400: {"type": "object", "properties": {"error": {"type": "string"}}},
        },
    )
    def post(self, request):
        serializer = PasswordResetConfirmInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uidb64 = serializer.validated_data["uidb64"]
        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]
        new_password_confirm = serializer.validated_data["new_password_confirm"]

        try:
            auth_password_reset_confirm(
                uidb64=uidb64,
                token=token,
                new_password=new_password,
                new_password_confirm=new_password_confirm,
            )
        except (InvalidTokenError, InvalidPasswordError) as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"message": "Đặt lại mật khẩu thành công! Bạn có thể đăng nhập bằng mật khẩu mới."},
            status=status.HTTP_200_OK,
        )
