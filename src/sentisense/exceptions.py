"""SentiSense API exceptions."""

from typing import Optional

import requests


class SentiSenseError(Exception):
    """Base exception for all SentiSense SDK errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[requests.Response] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response


class AuthenticationError(SentiSenseError):
    """Raised on 401 or 403 responses (invalid or missing API key)."""


class NotFoundError(SentiSenseError):
    """Raised on 404 responses."""


class RateLimitError(SentiSenseError):
    """Raised on 429 responses (rate limit exceeded)."""


class APIError(SentiSenseError):
    """Raised on other non-2xx responses."""


def _raise_for_status(response: requests.Response) -> None:
    """Raise a typed SentiSenseError for non-2xx responses."""
    if response.ok:
        return

    try:
        body = response.json()
        message = body.get("message") or body.get("error") or response.reason
    except (ValueError, KeyError):
        message = response.reason or f"HTTP {response.status_code}"

    status = response.status_code
    kwargs = dict(message=message, status_code=status, response=response)

    if status in (401, 403):
        raise AuthenticationError(**kwargs)
    elif status == 404:
        raise NotFoundError(**kwargs)
    elif status == 429:
        raise RateLimitError(**kwargs)
    else:
        raise APIError(**kwargs)
