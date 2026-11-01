# mangementlogistics/users/api/serializers.py
from rest_framework import serializers

from mangementlogistics.authentication.validators import validate_password_complexity
from mangementlogistics.users.constants import UserRole
from mangementlogistics.users.exceptions import InvalidPasswordError


class UserOutputSerializer(serializers.Serializer):
    """
    Serializer for returning safe public/admin user details.
    Password is strictly excluded.
    """
    id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.CharField()
    phone_number = serializers.CharField(allow_null=True)
    address = serializers.CharField(allow_null=True)
    is_active = serializers.BooleanField()


class UserCreateInputSerializer(serializers.Serializer):
    """
    Serializer for validating user creation request payload.
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    name = serializers.CharField(required=False, default="")
    role = serializers.ChoiceField(choices=UserRole.choices, default=UserRole.CUSTOMER)
    phone_number = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    address = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)

    def validate_password(self, value):
        try:
            validate_password_complexity(value)
        except InvalidPasswordError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value


class UserUpdateInputSerializer(serializers.Serializer):
    """
    Serializer for validating user update payload.
    """
    email = serializers.EmailField(required=False)
    name = serializers.CharField(required=False)
    role = serializers.ChoiceField(choices=UserRole.choices, required=False)
    phone_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    address = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class UserChangePasswordInputSerializer(serializers.Serializer):
    """
    Serializer for validating password change payload.
    """
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True, min_length=8, required=False)

    def validate(self, attrs):
        new_password = attrs.get("new_password")
        new_password_confirm = attrs.get("new_password_confirm")

        if new_password_confirm and new_password != new_password_confirm:
            raise serializers.ValidationError({"new_password_confirm": "Mật khẩu xác nhận không khớp."})

        if attrs.get("old_password") == new_password:
            raise serializers.ValidationError({"new_password": "Mật khẩu mới không được trùng với mật khẩu cũ."})

        try:
            validate_password_complexity(new_password)
        except InvalidPasswordError as exc:
            raise serializers.ValidationError({"new_password": str(exc)}) from exc

        return attrs
