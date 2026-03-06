"""SentiSense API client."""

from typing import Any, Dict, List, Optional

import requests

from sentisense.__about__ import __version__
from sentisense.exceptions import _raise_for_status


class SentiSenseClient:
    """Official Python client for the SentiSense market intelligence API.

    Usage::

        from sentisense import SentiSenseClient

        client = SentiSenseClient("your-api-key")
        price = client.get_stock_price("AAPL")
    """

    BASE_URL = "https://app.sentisense.ai"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "X-SentiSense-API-Key": api_key,
            "User-Agent": f"sentisense-python/{__version__}",
        })

    # ── Private HTTP helpers ────────────────────────────────────

    def _url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self.base_url}{path}"

    def _get(self, path: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        resp = self.session.get(self._url(path), **kwargs)
        _raise_for_status(resp)
        return resp

    def _post(self, path: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        resp = self.session.post(self._url(path), **kwargs)
        _raise_for_status(resp)
        return resp

    def _put(self, path: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        resp = self.session.put(self._url(path), **kwargs)
        _raise_for_status(resp)
        return resp

    def _delete(self, path: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        resp = self.session.delete(self._url(path), **kwargs)
        _raise_for_status(resp)
        return resp

    # ── Stock endpoints ─────────────────────────────────────────

    def get_stock_price(self, ticker: str) -> Dict[str, Any]:
        """Get real-time stock price for a single ticker."""
        return self._get("/api/v1/stocks/price", params={"ticker": ticker}).json()

    def get_stock_prices(self, tickers: List[str]) -> List[Dict[str, Any]]:
        """Get real-time stock prices for multiple tickers."""
        return self._get("/api/v1/stocks/prices", params={"tickers": ",".join(tickers)}).json()

    def get_stock_profile(self, ticker: str) -> Dict[str, Any]:
        """Get company profile for a stock."""
        return self._get(f"/api/v1/stocks/{ticker}/profile").json()

    def get_stock_chart(self, ticker: str, timeframe: str = "1M") -> Dict[str, Any]:
        """Get OHLCV chart data for a stock.

        Args:
            ticker: Stock ticker symbol.
            timeframe: Chart timeframe (e.g. "1D", "1W", "1M", "3M", "1Y").
        """
        return self._get("/api/v1/stocks/chart", params={"ticker": ticker, "timeframe": timeframe}).json()

    def get_all_stocks(self) -> List[str]:
        """Get all available stock tickers."""
        return self._get("/api/v1/stocks").json()

    def get_all_stocks_detailed(self) -> List[Dict[str, Any]]:
        """Get all stocks with company names and entity IDs."""
        return self._get("/api/v1/stocks/detailed").json()

    def get_market_status(self) -> Dict[str, Any]:
        """Get current market status (open/closed)."""
        return self._get("/api/v1/stocks/market-status").json()

    def get_fundamentals(
        self,
        ticker: str,
        timeframe: str = "quarterly",
        fiscal_period: Optional[str] = None,
        fiscal_year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get fundamental financial data for a stock.

        Args:
            ticker: Stock ticker symbol.
            timeframe: "quarterly" or "annual".
            fiscal_period: Filter by fiscal period (e.g. "Q1", "Q2").
            fiscal_year: Filter by fiscal year (e.g. 2025).
        """
        params: Dict[str, Any] = {"ticker": ticker, "timeframe": timeframe}
        if fiscal_period:
            params["fiscalPeriod"] = fiscal_period
        if fiscal_year:
            params["fiscalYear"] = fiscal_year
        return self._get("/api/v1/stocks/fundamentals", params=params).json()

    # ── Institutional flow endpoints ────────────────────────────

    def get_institutional_quarters(self) -> List[str]:
        """Get available 13F reporting quarters."""
        return self._get("/api/v1/institutional/quarters").json()

    def get_institutional_flows(self, report_date: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get institutional fund flows for a reporting quarter.

        Args:
            report_date: Quarter date string (e.g. "2025-03-31").
            limit: Maximum number of results.
        """
        return self._get(
            "/api/v1/institutional/flows",
            params={"reportDate": report_date, "limit": limit},
        ).json()

    def get_stock_holders(self, ticker: str, report_date: str) -> List[Dict[str, Any]]:
        """Get institutional holders for a specific stock.

        Args:
            ticker: Stock ticker symbol.
            report_date: Quarter date string (e.g. "2025-03-31").
        """
        return self._get(
            f"/api/v1/institutional/holders/{ticker}",
            params={"reportDate": report_date},
        ).json()

    def get_activist_positions(self, report_date: str) -> List[Dict[str, Any]]:
        """Get activist investor positions for a reporting quarter.

        Args:
            report_date: Quarter date string (e.g. "2025-03-31").
        """
        return self._get(
            "/api/v1/institutional/activist",
            params={"reportDate": report_date},
        ).json()
