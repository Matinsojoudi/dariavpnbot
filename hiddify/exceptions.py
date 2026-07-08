class HiddifyAPIError(Exception):
    """Base exception for Hiddify API errors."""

    pass


class HiddifyConnectionError(HiddifyAPIError):
    """Raised when the panel cannot be reached."""

    pass


class HiddifyNotFoundError(HiddifyAPIError):
    """Raised when a resource is not found (404)."""

    pass


class HiddifyAuthError(HiddifyAPIError):
    """Raised when authentication fails (401/403)."""

    pass
