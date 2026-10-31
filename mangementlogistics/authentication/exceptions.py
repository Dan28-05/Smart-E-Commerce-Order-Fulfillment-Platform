# mangementlogistics/authentication/exceptions.py


class InvalidCredentialsError(Exception):
    """Raised when user credentials (email or password) are incorrect."""


class InactiveAccountError(Exception):
    """Raised when the account is deactivated / inactive."""


class InvalidTokenError(Exception):
    """Raised when a JWT token is invalid or expired."""
