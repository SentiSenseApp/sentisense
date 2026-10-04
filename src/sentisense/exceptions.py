"""SentiSense API exceptions."""

from typing import Optional

import requests


class SentiSenseError(Exception):
    """Base exception for all SentiSense SDK errors.

    ``code`` is the API's machine-readable error code (the ``error`` field of the response
    body, for example ``"quota_exceeded"``), or ``None`` when the response carried none.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[requests.Response] = None,
        code: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response
        self.code = code


class AuthenticationError(SentiSenseError):
    """Raised on 401 or 403 responses (invalid or missing API key)."""


class NotFoundError(SentiSenseError):
    """Raised on 404 responses."""


class DeepHistoryUnavailable(SentiSenseError):
    """Raised when a deep chart range is still being assembled.

    The API answers ``202`` for ``10Y`` and ``MAX`` the first time a rarely-requested
    stock is asked for, while its history is built. It deliberately does not substitute
    a shorter range, so a successful response always carries the timeframe you asked
    for. Retry after a few seconds.
    """


class RateLimitError(SentiSenseError):
    """Raised on 429 responses. Check ``code`` to tell the two apart:

    - ``"rate_limit_exceeded"``: the per-minute limit. The client retries it after
      ``Retry-After`` before raising, so you see this only once retries are used up.
    - ``"quota_exceeded"``: the monthly allowance is used up. It is raised on the first
      response without retrying, and ``message`` says when the allowance resets.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[requests.Response] = None,
        retry_after: Optional[int] = None,
        code: Optional[str] = None,
    ):
        super().__init__(message, status_code, response, code=code)
        self.retry_after = retry_after


class TemporarilyUnavailable(SentiSenseError):
    """Raised when the server is briefly out of upstream capacity.

    The API answers ``503`` with a ``Retry-After`` header saying when it expects to be
    ready. The client honours that header automatically, so you normally never see this;
    it is raised only when the requested wait is longer than the client is willing to
    sleep for. ``retry_after`` carries the server's figure in seconds, so a batch job can
    keep the results it already has and resume later rather than retrying into a server
    that has told you it is not ready.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[requests.Response] = None,
        retry_after: Optional[float] = None,
    ):
        super().__init__(message, status_code, response)
        self.retry_after = retry_after


class APIError(SentiSenseError):
    """Raised on other non-2xx responses."""


def _raise_for_status(response: requests.Response) -> None:
    """Raise a typed SentiSenseError for non-2xx responses."""
    if response.ok:
        return

    code: Optional[str] = None
    try:
        body = response.json()
        message = body.get("message") or body.get("error") or response.reason
        if isinstance(body.get("error"), str):
            code = body["error"]
    except (ValueError, KeyError, AttributeError):
        message = response.reason or f"HTTP {response.status_code}"

    status = response.status_code
    kwargs = dict(message=message, status_code=status, response=response, code=code)

    if status in (401, 403):
        raise AuthenticationError(**kwargs)
    elif status == 404:
        raise NotFoundError(**kwargs)
    elif status == 429:
        ra_header = response.headers.get("Retry-After")
        retry_after: Optional[int] = None
        if ra_header:
            try:
                retry_after = int(ra_header)
            except ValueError:
                pass
        raise RateLimitError(**kwargs, retry_after=retry_after)
    else:
        raise APIError(**kwargs)
