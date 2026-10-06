# mangementlogistics/users/api/serializers.py
from rest_framework import serializers

from mangementlogistics.users.constants import UserRole


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
    password = serializers.CharField(write_only=True, min_length=6)
    name = serializers.CharField(required=False, default="")
    role = serializers.ChoiceField(choices=UserRole.choices, default=UserRole.CUSTOMER)
    phone_number = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    address = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class UserUpdateInputSerializer(serializers.Serializer):
    """
    Serializer for validating user update payload.
    """
    email = serializers.EmailField(required=False)
    name = serializers.CharField(required=False)
    role = serializers.ChoiceField(choices=UserRole.choices, required=False)
    phone_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    address = serializers.CharField(required=False, allow_null=True, allow_blank=True)
