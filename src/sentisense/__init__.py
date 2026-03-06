"""SentiSense — Official Python SDK for the SentiSense market intelligence API."""

from sentisense.__about__ import __version__
from sentisense.client import SentiSenseClient
from sentisense.exceptions import (
    APIError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    SentiSenseError,
)

__all__ = [
    "__version__",
    "APIError",
    "AuthenticationError",
    "NotFoundError",
    "RateLimitError",
    "SentiSenseClient",
    "SentiSenseError",
]
