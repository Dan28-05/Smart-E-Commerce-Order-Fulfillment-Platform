# mangementlogistics/authentication/api/serializers.py
from rest_framework import serializers


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
