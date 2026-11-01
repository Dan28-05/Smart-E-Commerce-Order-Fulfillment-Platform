# mangementlogistics/authentication/api/serializers.py
from rest_framework import serializers

from mangementlogistics.authentication.validators import validate_password_complexity
from mangementlogistics.users.exceptions import InvalidPasswordError


class UserAuthOutputSerializer(serializers.Serializer):
    """
    Public/safe serialized user data returned on login.
    """
    id = serializers.IntegerField()
    email = serializers.EmailField()
    name = serializers.CharField()
    role = serializers.CharField()
    phone_number = serializers.CharField(allow_null=True)
    address = serializers.CharField(allow_null=True)


class LoginInputSerializer(serializers.Serializer):
    """
    Credentials for user login.
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)


class LoginOutputSerializer(serializers.Serializer):
    """
    Payload returned upon successful authentication.
    """
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserAuthOutputSerializer()


class TokenRefreshInputSerializer(serializers.Serializer):
    """
    Payload for requesting a refreshed access token.
    """
    refresh = serializers.CharField(required=True)


class TokenRefreshOutputSerializer(serializers.Serializer):
    """
    Payload returned after token refresh.
    """
    access = serializers.CharField()


class TokenVerifyInputSerializer(serializers.Serializer):
    """
    Payload for verifying token validity.
    """
    token = serializers.CharField(required=True)


class LogoutInputSerializer(serializers.Serializer):
    """
    Payload for logging out / invalidating token.
    """
    refresh = serializers.CharField(required=False, default="")


class ChangePasswordInputSerializer(serializers.Serializer):
    """
    Payload for changing current user's password.
    """
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(required=True, write_only=True, min_length=8)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "Mật khẩu xác nhận không khớp."})

        if attrs["old_password"] == attrs["new_password"]:
            raise serializers.ValidationError({"new_password": "Mật khẩu mới không được trùng với mật khẩu cũ."})

        try:
            validate_password_complexity(attrs["new_password"])
        except InvalidPasswordError as exc:
            raise serializers.ValidationError({"new_password": str(exc)}) from exc

        return attrs


class PasswordResetRequestInputSerializer(serializers.Serializer):
    """
    Payload for requesting password reset via email.
    """
    email = serializers.EmailField(required=True)


class PasswordResetValidateTokenInputSerializer(serializers.Serializer):
    """
    Payload for checking if a reset token is valid.
    """
    uidb64 = serializers.CharField(required=True)
    token = serializers.CharField(required=True)


class PasswordResetConfirmInputSerializer(serializers.Serializer):
    """
    Payload for setting a new password using reset token.
    """
    uidb64 = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(required=True, write_only=True, min_length=8)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "Mật khẩu xác nhận không khớp."})

        try:
            validate_password_complexity(attrs["new_password"])
        except InvalidPasswordError as exc:
            raise serializers.ValidationError({"new_password": str(exc)}) from exc

        return attrs
