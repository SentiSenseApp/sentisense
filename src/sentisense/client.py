"""SentiSense API client."""

import random
import time
from typing import Any, Dict, List, Optional

import requests

from sentisense.__about__ import __version__
from sentisense.exceptions import SentiSenseError, _raise_for_status


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
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
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

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        url = self._url(path)
        for attempt in range(self.max_retries + 1):
            resp = getattr(self.session, method)(url, **kwargs)
            if resp.ok:
                return resp
            is_retryable = resp.status_code == 429 or resp.status_code >= 500
            if is_retryable and attempt < self.max_retries:
                if resp.status_code == 429:
                    ra = resp.headers.get("Retry-After")
                    delay = float(ra) if ra else 60.0
                else:
                    delay = min(1.0 * (2 ** attempt), 60.0) + random.random()
                time.sleep(delay)
                continue
            _raise_for_status(resp)
        raise SentiSenseError("All retries exhausted")

    def _get(self, path: str, **kwargs: Any) -> requests.Response:
        return self._request("get", path, **kwargs)

    def _post(self, path: str, **kwargs: Any) -> requests.Response:
        return self._request("post", path, **kwargs)

    def _put(self, path: str, **kwargs: Any) -> requests.Response:
        return self._request("put", path, **kwargs)

    def _delete(self, path: str, **kwargs: Any) -> requests.Response:
        return self._request("delete", path, **kwargs)

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

    def get_similar_stocks(self, ticker: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get peer/similar stocks with current prices.

        Args:
            ticker: Stock ticker symbol (e.g., ``"AAPL"``).
            limit: Maximum number of results (default 5).

        Returns:
            List of ``{symbol, name, kbEntityId, price, changePercent}``.
        """
        return self._get(f"/api/v1/stocks/{ticker}/similar", params={"limit": limit}).json()

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

    def get_institutional_flows(self, report_date: str, limit: int = 50) -> Dict[str, Any]:
        """Get institutional fund flows for a reporting quarter.

        Returns a preview-wrapped dict: ``{isPreview, previewReason, data: {inflows, outflows}}``.
        Access flows via ``result["data"]["inflows"]`` and ``result["data"]["outflows"]``.

        Args:
            report_date: Quarter date string (e.g. "2025-12-31").
            limit: Maximum number of results per direction.
        """
        return self._get(
            "/api/v1/institutional/flows",
            params={"reportDate": report_date, "limit": limit},
        ).json()

    def get_stock_holders(self, ticker: str, report_date: str) -> Dict[str, Any]:
        """Get institutional holders for a specific stock.

        Returns a preview-wrapped dict: ``{isPreview, previewReason, data: {ticker, companyName, ...}}``.
        Access holders via ``result["data"]["holders"]``.

        Args:
            ticker: Stock ticker symbol.
            report_date: Quarter date string (e.g. "2025-12-31").
        """
        return self._get(
            f"/api/v1/institutional/holders/{ticker}",
            params={"reportDate": report_date},
        ).json()

    def get_activist_positions(self, report_date: str) -> List[Dict[str, Any]]:
        """Get activist investor positions for a reporting quarter.

        Args:
            report_date: Quarter date string (e.g. "2025-12-31").
        """
        return self._get(
            "/api/v1/institutional/activist",
            params={"reportDate": report_date},
        ).json()

    # ── Insider trading endpoints ───────────────────────────────

    def get_insider_activity(self, lookback_days: int = 90) -> Dict[str, Any]:
        """Get market-wide insider activity: top buys and sells aggregated by ticker.

        PRO-gated. All tiers return a wrapper: ``{isPreview, previewReason, data}``.
        Free/unauthenticated users receive a truncated preview (top 5 per direction).
        Access data via ``result["data"]``.

        Args:
            lookback_days: Number of days to look back (1-365). Default 90.
        """
        return self._get("/api/v1/insider/activity", params={"lookbackDays": lookback_days}).json()

    def get_insider_trades(self, ticker: str, lookback_days: int = 90) -> Dict[str, Any]:
        """Get individual insider transactions for a specific stock.

        PRO-gated. All tiers return a wrapper: ``{isPreview, previewReason, data}``.
        Free users receive a preview (top 5 transactions). Access trades via ``result["data"]``.

        Args:
            ticker: Stock ticker symbol (e.g., ``"AAPL"``).
            lookback_days: Number of days to look back (1-365). Default 90.
        """
        return self._get(
            f"/api/v1/insider/trades/{ticker.upper()}",
            params={"lookbackDays": lookback_days},
        ).json()

    def get_insider_cluster_buys(self, lookback_days: int = 90) -> Dict[str, Any]:
        """Get cluster buy signals: stocks where 3+ distinct insiders bought recently.

        PRO-gated. All tiers return a wrapper: ``{isPreview, previewReason, data}``.
        Free users receive a preview (top 3 signals). Access data via ``result["data"]``.

        Args:
            lookback_days: Number of days to look back (1-365). Default 90.
        """
        return self._get("/api/v1/insider/cluster-buys", params={"lookbackDays": lookback_days}).json()

    # ── Politicians trading endpoints ──────────────────────────

    def get_politician_activity(self, lookback_days: int = 90) -> Dict[str, Any]:
        """Get recent congressional STOCK Act trading activity across all politicians.

        PRO-gated. Free/unauthenticated users receive a preview (top 5 trades)
        with ``isPreview: true`` in the response. Access trades via ``result["data"]``.

        Args:
            lookback_days: Number of days to look back (1-365). Default 90.
        """
        return self._get("/api/v1/politicians/activity", params={"lookbackDays": lookback_days}).json()

    def get_politician_filings(self, ticker: str, lookback_days: int = 90) -> Dict[str, Any]:
        """Get congressional trades for a specific stock.

        PRO-gated. Free users receive a preview (top 3 trades)
        with ``isPreview: true`` in the response. Access trades via ``result["data"]``.

        Args:
            ticker: Stock ticker symbol (e.g., ``"NVDA"``).
            lookback_days: Number of days to look back (1-365). Default 90.
        """
        return self._get(
            f"/api/v1/politicians/filings/{ticker.upper()}",
            params={"lookbackDays": lookback_days},
        ).json()

    def get_politician_members(self) -> Dict[str, Any]:
        """Get all tracked politicians with trading summary statistics.

        PRO-gated. Free users receive a preview (top 5 members)
        with ``isPreview: true`` in the response. Access members via ``result["data"]``.
        """
        return self._get("/api/v1/politicians/members").json()

    def get_politician_member(self, slug: str) -> Dict[str, Any]:
        """Get detailed profile for a single politician.

        Returns profile summary, recent trades, and top tickers. PRO-gated.
        Free users receive a preview-wrapped response.
        Access detail via ``result["data"]``.

        Args:
            slug: Politician URL slug (e.g., ``"nancy-pelosi"``). Get slugs from ``get_politician_members()``.
        """
        return self._get(f"/api/v1/politicians/member/{slug}").json()

    # ── Insights endpoints ──────────────────────────────────────

    def get_stock_insights(
        self,
        ticker: str,
        urgency: Optional[str] = None,
        insight_type: Optional[str] = None,
    ) -> Any:
        """Get AI-generated insights for a specific stock.

        PRO-gated. Free/unauthenticated users receive a preview with ``isPreview: true``:
        the top 3 insights in full, plus a ``locked`` list of metadata-only entries
        (type, urgency, timestamp) showing what additional signals exist.

        Args:
            ticker: Stock ticker symbol (e.g., ``"AAPL"``).
            urgency: Filter by urgency level -- ``"low"``, ``"medium"``, or ``"high"``.
            insight_type: Filter by insight type (e.g., ``"insider_buy_signal"``).

        Returns:
            List of insight objects for PRO users, or preview dict for free users.
        """
        params: Dict[str, Any] = {}
        if urgency:
            params["urgency"] = urgency
        if insight_type:
            params["insightType"] = insight_type
        return self._get(f"/api/v1/insights/stock/{ticker.upper()}", params=params).json()

    def get_market_insights(self) -> Any:
        """Get AI-generated market-level insights.

        PRO-gated. Free/unauthenticated users receive a preview with ``isPreview: true``:
        the top 5 insights in full, plus a ``locked`` list of metadata-only entries.

        Returns:
            List of insight objects for PRO users, or preview dict for free users.
        """
        return self._get("/api/v1/insights/market").json()

    def get_insight_types(self, ticker: str) -> List[str]:
        """Get available insight types for a specific stock.

        No authentication required. Returns a list of insight type strings
        such as ``"insider_buy_signal"``, ``"institutional_position_change"``, or ``"volume_anomaly_high"``.

        Args:
            ticker: Stock ticker symbol (e.g., ``"AAPL"``).
        """
        return self._get(f"/api/v1/insights/stock/{ticker.upper()}/types").json()

    # ── Document & news endpoints ───────────────────────────────

    def get_documents_by_ticker(
        self,
        ticker: str,
        source: Optional[str] = None,
        days: Optional[int] = None,
        hours: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get document metrics for a stock ticker.

        Returns document objects with sentiment scores, reliability, source URL,
        and per-entity sentiment classification. Each document includes a
        ``sentiment`` array of objects with ``ticker``, ``name``, ``entityId``,
        ``entityType``, and ``sentiment`` fields.

        Args:
            ticker: Stock ticker symbol.
            source: Filter by source — "news", "reddit", "x", or "substack".
            days: Look back N days.
            hours: Look back N hours.
            limit: Maximum number of results.
        """
        params: Dict[str, Any] = {}
        if source:
            params["source"] = source
        if days is not None:
            params["days"] = days
        if hours is not None:
            params["hours"] = hours
        if limit is not None:
            params["limit"] = limit
        return self._get(f"/api/v1/documents/ticker/{ticker}", params=params).json()

    def get_documents_by_ticker_range(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        source: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get news articles for a stock within a date range.

        Args:
            ticker: Stock ticker symbol.
            start_date: Start date (e.g. "2025-01-01").
            end_date: End date (e.g. "2025-01-31").
            source: Filter by source — "news", "reddit", "x", or "substack".
            limit: Maximum number of results.
        """
        params: Dict[str, Any] = {"startDate": start_date, "endDate": end_date}
        if source:
            params["source"] = source
        if limit is not None:
            params["limit"] = limit
        return self._get(f"/api/v1/documents/ticker/{ticker}/range", params=params).json()

    def get_documents_by_entity(
        self,
        entity_id: str,
        source: Optional[str] = None,
        days: Optional[int] = None,
        hours: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get documents for a knowledge base entity.

        Args:
            entity_id: KB entity ID.
            source: Filter by source — "news", "reddit", "x", or "substack".
            days: Look back N days.
            hours: Look back N hours.
            limit: Maximum number of results.
        """
        params: Dict[str, Any] = {}
        if source:
            params["source"] = source
        if days is not None:
            params["days"] = days
        if hours is not None:
            params["hours"] = hours
        if limit is not None:
            params["limit"] = limit
        return self._get(f"/api/v1/documents/entity/{entity_id}", params=params).json()

    def search_documents(
        self,
        query: str,
        source: Optional[str] = None,
        days: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Search news and social posts with a natural language query.

        Args:
            query: Search query string.
            source: Filter by source — "news", "reddit", "x", or "substack".
            days: Look back N days.
            limit: Maximum number of results.
        """
        params: Dict[str, Any] = {"query": query}
        if source:
            params["source"] = source
        if days is not None:
            params["days"] = days
        if limit is not None:
            params["limit"] = limit
        return self._get("/api/v1/documents/search", params=params).json()

    def get_documents_by_source(
        self,
        source: str,
        days: Optional[int] = None,
        hours: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get latest documents from a specific source.

        Args:
            source: Source type — "news", "reddit", "x", or "substack".
            days: Look back N days.
            hours: Look back N hours.
            limit: Maximum number of results.
        """
        params: Dict[str, Any] = {}
        if days is not None:
            params["days"] = days
        if hours is not None:
            params["hours"] = hours
        if limit is not None:
            params["limit"] = limit
        return self._get(f"/api/v1/documents/source/{source}", params=params).json()

    def get_stories(
        self,
        limit: Optional[int] = None,
        days: Optional[int] = None,
        offset: Optional[int] = None,
        filter_hours: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get AI-curated news story clusters.

        Returns story objects with title, sentiment, impact score, and tickers.
        Each story includes a ``brokeAt`` field (epoch seconds) indicating when
        the story broke.

        Args:
            limit: Maximum number of stories.
            days: Look back N days.
            offset: Pagination offset.
            filter_hours: Filter stories from last N hours.
        """
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if days is not None:
            params["days"] = days
        if offset is not None:
            params["offset"] = offset
        if filter_hours is not None:
            params["filterHours"] = filter_hours
        return self._get("/api/v1/documents/stories", params=params).json()

    def get_stories_by_ticker(self, ticker: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get news stories for a specific stock.

        Args:
            ticker: Stock ticker symbol.
            limit: Maximum number of stories.
        """
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        return self._get(f"/api/v1/documents/stories/ticker/{ticker}", params=params).json()

    # ── Market summary endpoint ────────────────────────────────

    def get_market_summary(self) -> Dict[str, Any]:
        """Get the AI-generated market summary.

        Returns a dict with ``headline``, ``expandedContent`` (markdown),
        ``topActiveStocks``, ``totalMentions``, ``lastUpdated``, and
        ``generatedAt`` fields.
        """
        return self._get("/api/v1/market-summary").json()

    # ── Metrics endpoints (v2) ──────────────────────────────────

    def get_metrics(
        self,
        symbol: str,
        metric_type: str = "mentions",
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        max_data_points: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get time series metrics for a stock (mentions, sentiment, etc.).

        Args:
            symbol: Stock ticker symbol (e.g. "AAPL").
            metric_type: Metric to retrieve — "mentions", "sentiment",
                "sentisense", or "social_dominance".
            start_time: Start of window as epoch milliseconds.
            end_time: End of window as epoch milliseconds.
            max_data_points: Maximum number of data points to return.
        """
        params: Dict[str, Any] = {}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        if max_data_points is not None:
            params["maxDataPoints"] = max_data_points
        return self._get(
            f"/api/v2/metrics/entity/{symbol}/metric/{metric_type}",
            params=params,
        ).json()

    def get_metrics_distribution(
        self,
        symbol: str,
        metric_type: str = "mentions",
        dimension: str = "source",
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get metric distribution by dimension (e.g., mentions by source).

        Args:
            symbol: Stock ticker symbol (e.g. "AAPL").
            metric_type: Metric to retrieve — "mentions", "sentiment",
                "sentisense", or "social_dominance".
            dimension: Dimension to break down by (e.g. "source").
            start_time: Start of window as epoch milliseconds.
            end_time: End of window as epoch milliseconds.
        """
        params: Dict[str, Any] = {"dimension": dimension}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        return self._get(
            f"/api/v2/metrics/entity/{symbol}/distribution/{metric_type}",
            params=params,
        ).json()

    # ── Entity metrics endpoints (DEPRECATED — use get_metrics / get_metrics_distribution) ──

    def get_mentions(
        self,
        symbol: str,
        source: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get mention data for a stock across news and social media.

        .. deprecated::
            Use :meth:`get_metrics` with ``metric_type="mentions"`` instead.
            This method hits the v1 entity-metrics endpoint which returns empty data.

        Args:
            symbol: Stock ticker symbol.
            source: Filter by source — "news", "reddit", "x", or "substack".
            start_date: Start date (e.g. "2025-01-01").
            end_date: End date (e.g. "2025-01-31").
        """
        params: Dict[str, Any] = {}
        if source:
            params["source"] = source
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        return self._get(f"/api/v1/entity-metrics/stocks/{symbol}/mentions", params=params).json()

    def get_mention_count(
        self,
        symbol: str,
        source: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get total mention count for a stock.

        .. deprecated::
            Use :meth:`get_metrics` with ``metric_type="mentions"`` instead.
            This method hits the v1 entity-metrics endpoint which returns empty data.

        Args:
            symbol: Stock ticker symbol.
            source: Filter by source — "news", "reddit", "x", or "substack".
            start_date: Start date (e.g. "2025-01-01").
            end_date: End date (e.g. "2025-01-31").
        """
        params: Dict[str, Any] = {}
        if source:
            params["source"] = source
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        return self._get(f"/api/v1/entity-metrics/stocks/{symbol}/mentions/count", params=params).json()

    def get_mention_count_by_source(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get mention counts broken down by source (news, reddit, x, substack).

        .. deprecated::
            Use :meth:`get_metrics_distribution` with ``metric_type="mentions"``
            and ``dimension="source"`` instead.
            This method hits the v1 entity-metrics endpoint which returns empty data.

        Args:
            symbol: Stock ticker symbol.
            start_date: Start date (e.g. "2025-01-01").
            end_date: End date (e.g. "2025-01-31").
        """
        params: Dict[str, Any] = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        return self._get(f"/api/v1/entity-metrics/stocks/{symbol}/mentions/count/by-source", params=params).json()

    def get_sentiment(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get sentiment data for a stock.

        .. deprecated::
            Use :meth:`get_metrics` with ``metric_type="sentiment"`` instead.
            This method hits the v1 entity-metrics endpoint which returns empty data.

        Args:
            symbol: Stock ticker symbol.
            start_date: Start date (e.g. "2025-01-01").
            end_date: End date (e.g. "2025-01-31").
        """
        params: Dict[str, Any] = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        return self._get(f"/api/v1/entity-metrics/stocks/{symbol}/sentiment", params=params).json()

    def get_sentiment_by_source(self, symbol: str, date: Optional[str] = None) -> Dict[str, Any]:
        """Get sentiment broken down by source (news, reddit, x, substack).

        .. deprecated::
            Use :meth:`get_metrics_distribution` with ``metric_type="sentiment"``
            and ``dimension="source"`` instead.
            This method hits the v1 entity-metrics endpoint which returns empty data.

        Args:
            symbol: Stock ticker symbol.
            date: Specific date (e.g. "2025-01-15").
        """
        params: Dict[str, Any] = {}
        if date:
            params["date"] = date
        return self._get(f"/api/v1/entity-metrics/stocks/{symbol}/sentiment/by-source", params=params).json()

    def get_average_sentiment(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get average sentiment score for a stock.

        .. deprecated::
            Use :meth:`get_metrics` with ``metric_type="sentiment"`` instead.
            This method hits the v1 entity-metrics endpoint which returns empty data.

        Args:
            symbol: Stock ticker symbol.
            start_date: Start date (e.g. "2025-01-01").
            end_date: End date (e.g. "2025-01-31").
        """
        params: Dict[str, Any] = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        return self._get(f"/api/v1/entity-metrics/stocks/{symbol}/sentiment/average", params=params).json()
