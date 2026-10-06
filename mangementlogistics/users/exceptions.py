# mangementlogistics/users/exceptions.py


class UserNotFoundError(Exception):
    """Raised when a user is not found."""
    pass


class InvalidPasswordError(Exception):
    """Raised when the provided password is wrong or does not meet requirements."""
    pass


class DuplicateEmailError(Exception):
    """Raised when attempting to create/update a user with an already existing email."""
    pass
