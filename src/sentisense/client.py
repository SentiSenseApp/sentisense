"""SentiSense API client."""

import random
import time
from typing import Any, Dict, List, Optional, Type, TypeVar

import requests

from sentisense.__about__ import __version__
from sentisense.exceptions import SentiSenseError, _raise_for_status
from sentisense.types import (
    APIModel,
    ClusterBuy,
    CompanyKpis,
    CongressTrade,
    Document,
    EarningsCalendar,
    DocumentSearchResponse,
    FundamentalsPeriod,
    EtfAnalystAggregate,
    EtfHoldings,
    EtfInfo,
    EtfInsiderAggregate,
    EtfSentimentAggregate,
    Insight,
    InsiderActivity,
    InsiderTrade,
    InstitutionalFlow,
    InstitutionalFlows,
    KpiCoverage,
    KpiCoverageEntry,
    KpiSeries,
    KpiTypeEntry,
    MarketStatus,
    MarketSummary,
    PoliticianDetail,
    PoliticianSummary,
    PreviewResult,
    Quarter,
    SimilarStock,
    StockDetail,
    StockPrice,
    StockQuote,
    Story,
    TrackerListResponse,
    TrackerSnapshot,
)

_M = TypeVar("_M", bound=APIModel)


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

    # ── Response parsing helpers ─────────────────────────────────

    def _parse(self, json_data: Any, cls: Type[_M]) -> _M:
        """Parse a JSON response into a typed model."""
        return cls.from_dict(json_data)

    def _parse_list(self, json_data: Any, cls: Type[_M]) -> List[_M]:
        """Parse a JSON array into a list of typed models."""
        return [cls.from_dict(item) for item in json_data]

    def _unwrap(
        self,
        json_data: dict,
        *,
        item_cls: Optional[Type[_M]] = None,
        list_cls: Optional[Type[_M]] = None,
    ) -> PreviewResult:
        """Auto-unwrap the preview envelope and parse into typed models.

        PRO-gated endpoints return ``{isPreview, previewReason, data}``,
        plus ``totalCount`` on preview list responses. This strips the
        envelope, parses ``data``, and returns a
        :class:`~sentisense.types.PreviewResult` with ``.is_preview``,
        ``.preview_reason`` and ``.total_count`` metadata.
        """
        is_preview = json_data.get("isPreview", False)
        preview_reason = json_data.get("previewReason")
        total_count = json_data.get("totalCount")
        data = json_data.get("data", json_data)

        if list_cls is not None and isinstance(data, list):
            parsed = [list_cls.from_dict(item) for item in data]
        elif item_cls is not None and isinstance(data, dict):
            parsed = item_cls.from_dict(data)
        else:
            parsed = data

        return PreviewResult(parsed, is_preview, preview_reason, total_count)

    # ── Stock endpoints ─────────────────────────────────────────

    def get_stock_price(self, ticker: str) -> StockPrice:
        """Get real-time stock price for a single ticker.

        ``currentPrice`` is always the regular-session price (live last trade during RTH,
        most recent regular-session close otherwise). During pre-market and after-hours
        the response includes a nested ``extendedHours`` object with the live extended-hours
        price plus its change vs ``currentPrice``::

            {"session": "pre" | "post", "price": float, "change": float, "changePercent": float}

        The ``extendedHours`` field is absent (``None``) during RTH, overnight, and weekends.
        """
        return self._parse(self._get("/api/v1/stocks/price", params={"ticker": ticker}).json(), StockPrice)

    def get_stock_quote(self, ticker: str) -> StockQuote:
        """Get aggregate quote snapshot for a ticker.

        Returns live price, today OHLC, 52-week range, market cap, P/E,
        EPS TTM, and dividend yield in a single call. All fields except
        ``ticker`` may be ``None`` when upstream data is unavailable.

        ``currentPrice`` is always the regular-session price. During pre-market and
        after-hours, the response includes a nested ``extendedHours`` object — see
        :meth:`get_stock_price` for the shape.

        Args:
            ticker: Stock ticker symbol (e.g., ``"AAPL"``).
        """
        return self._parse(self._get(f"/api/v1/stocks/{ticker}/quote").json(), StockQuote)

    def get_stock_prices(self, tickers: List[str]) -> List[StockPrice]:
        """Get real-time stock prices for multiple tickers.

        See :meth:`get_stock_price` for the per-ticker payload shape including the
        nested ``extendedHours`` object during pre/post sessions.
        """
        return self._parse_list(self._get("/api/v1/stocks/prices", params={"tickers": ",".join(tickers)}).json(), StockPrice)

    def get_stock_profile(self, ticker: str) -> Dict[str, Any]:
        """Get company profile for a stock."""
        return self._get(f"/api/v1/stocks/{ticker}/profile").json()

    def get_stock_entities(self, ticker: str) -> List[Dict[str, Any]]:
        """Get the tracked entities related to a stock (executives, products, organizations).

        Each entry carries ``entityId``, ``name``, and ``type``.

        Args:
            ticker: Stock ticker symbol (e.g., ``"AAPL"``).
        """
        return self._get(f"/api/v1/stocks/{ticker}/entities").json()

    def get_similar_stocks(self, ticker: str, limit: int = 5) -> List[SimilarStock]:
        """Get peer/similar stocks with current prices.

        Args:
            ticker: Stock ticker symbol (e.g., ``"AAPL"``).
            limit: Maximum number of results (default 5).
        """
        return self._parse_list(self._get(f"/api/v1/stocks/{ticker}/similar", params={"limit": limit}).json(), SimilarStock)

    def get_stock_chart(self, ticker: str, timeframe: str = "1M") -> Dict[str, Any]:
        """Get OHLCV chart data for a stock.

        Args:
            ticker: Stock ticker symbol.
            timeframe: Chart timeframe. One of "1D", "5D", "1W", "1M", "3M", "6M", "1Y", "ALL".

        Each bar carries: ``timestamp`` (Unix ms), ``date`` (display string), ``open``,
        ``high``, ``low``, ``close``, ``volume``, and ``session`` ("pre" / "regular" /
        "post" for intraday timeframes; ``None`` for daily and weekly bars).
        """
        return self._get("/api/v1/stocks/chart", params={"ticker": ticker, "timeframe": timeframe}).json()

    def get_all_stocks(self) -> List[str]:
        """Get all available stock tickers."""
        return self._get("/api/v1/stocks").json()

    def get_all_stocks_detailed(self) -> List[StockDetail]:
        """Get all stocks with company names and entity IDs."""
        return self._parse_list(self._get("/api/v1/stocks/detailed").json(), StockDetail)

    def get_market_status(self) -> MarketStatus:
        """Get current market status (open/closed)."""
        return self._parse(self._get("/api/v1/stocks/market-status").json(), MarketStatus)

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

    def get_current_fundamentals(self, ticker: str) -> Dict[str, Any]:
        """Get the most recent fundamentals snapshot for a ticker.

        Args:
            ticker: Stock ticker symbol.
        """
        return self._get(
            "/api/v1/stocks/fundamentals/current", params={"ticker": ticker}
        ).json()

    def get_historical_revenue(self, ticker: str) -> Dict[str, Any]:
        """Get historical revenue data for a ticker.

        Args:
            ticker: Stock ticker symbol.
        """
        return self._get(
            "/api/v1/stocks/fundamentals/historical/revenue", params={"ticker": ticker}
        ).json()

    def get_short_interest(self, ticker: str) -> Dict[str, Any]:
        """Get short interest metrics (FINRA bi-monthly settlement data).

        Args:
            ticker: Stock ticker symbol (e.g. ``"GME"``).
        """
        return self._get(
            "/api/v1/stocks/short-interest", params={"ticker": ticker}
        ).json()

    def get_float(self, ticker: str) -> Dict[str, Any]:
        """Get float information (shares available for public trading).

        Args:
            ticker: Stock ticker symbol.
        """
        return self._get("/api/v1/stocks/float", params={"ticker": ticker}).json()

    def get_short_volume(self, ticker: str) -> Dict[str, Any]:
        """Get daily short-sale volume (FINRA), distinct from short interest.

        Args:
            ticker: Stock ticker symbol.
        """
        return self._get(
            "/api/v1/stocks/short-volume", params={"ticker": ticker}
        ).json()

    # ── Institutional flow endpoints ────────────────────────────

    def get_institutional_quarters(self) -> List[Quarter]:
        """Get available 13F reporting quarters."""
        return self._parse_list(self._get("/api/v1/institutional/quarters").json(), Quarter)

    def get_institutional_flows(self, report_date: Optional[str] = None, limit: int = 50) -> PreviewResult[InstitutionalFlows]:
        """Get institutional fund flows for a reporting quarter.

        Auto-unwrapped. Access flows via ``result.inflows`` and ``result.outflows``.
        Check ``result.is_preview`` for tier status.

        Args:
            report_date: Quarter date string (e.g. "2025-12-31"). Optional: omit it to
                get the latest available quarter, which may be a still-open one holding
                only early filers. The response then carries ``reportDate`` plus
                ``isPending`` and filer coverage counts so a partial quarter is labeled.
            limit: Maximum number of results per direction.
        """
        params: Dict[str, Any] = {"limit": limit}
        if report_date is not None:
            params["reportDate"] = report_date
        return self._unwrap(
            self._get("/api/v1/institutional/flows", params=params).json(),
            item_cls=InstitutionalFlows,
        )

    def get_stock_holders(self, ticker: str, report_date: str) -> PreviewResult:
        """Get institutional holders for a specific stock.

        Auto-unwrapped. Check ``result.is_preview`` for tier status.

        Args:
            ticker: Stock ticker symbol.
            report_date: Quarter date string (e.g. "2025-12-31").
        """
        return self._unwrap(
            self._get(f"/api/v1/institutional/holders/{ticker}", params={"reportDate": report_date}).json(),
        )

    def get_activist_positions(self, report_date: str) -> PreviewResult[List[Dict[str, Any]]]:
        """Get activist investor positions for a reporting quarter.

        Auto-unwrapped. Check ``result.is_preview`` for tier status.

        Args:
            report_date: Quarter date string (e.g. "2025-12-31").
        """
        return self._unwrap(
            self._get("/api/v1/institutional/activist", params={"reportDate": report_date}).json(),
        )

    def get_institution_detail(self, slug_or_cik: str) -> PreviewResult[Dict[str, Any]]:
        """Get full profile, summary stats, and current-quarter holdings for an institutional filer.

        Auto-unwrapped. Check ``result.is_preview`` for tier status. PRO users
        receive the full holdings array; free users receive the top 10 holdings.

        Args:
            slug_or_cik: URL slug (e.g. ``"Berkshire-Hathaway"``) or numeric SEC CIK.
        """
        return self._unwrap(
            self._get(f"/api/v1/institutional/institution/{slug_or_cik}").json(),
        )

    def list_institutions(
        self,
        *,
        category: Optional[str] = None,
        min_aum_usd: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
        sort: str = "aumDesc",
        quarter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Discover institutions: a paginated, AUM-ranked list of filers.

        Lets you find what to query without knowing slugs upfront. Each institution
        is rolled up by parent filer, so a multi-filer manager (e.g. Vanguard) appears
        once with combined AUM. Summary only; use :meth:`get_institution_detail` for
        a filer's full holdings.

        Returns the ``data`` object::

            {"quarter", "totalCount", "offset", "limit", "institutions": [
                {"cik", "urlSlug", "displayName", "filerCategory", "totalValueUsd",
                 "holdingsCount", "multiCikRollup", "childCikCount"}, ...]}

        Args:
            category: Filer category to filter by (e.g. ``"HEDGE_FUND"``). One of
                ``INDEX_FUND, HEDGE_FUND, ACTIVIST, PENSION, BANK, INSURANCE,
                MUTUAL_FUND, SOVEREIGN_WEALTH, ENDOWMENT, OTHER``.
            min_aum_usd: Minimum total AUM in USD (e.g. ``10_000_000_000``).
            limit: Page size (default 50, max 200).
            offset: Pagination offset.
            sort: ``"aumDesc"`` (default), ``"aumAsc"``, or ``"nameAsc"``.
            quarter: AUM snapshot quarter as ``YYYYQN`` (e.g. ``"2026Q1"``);
                defaults to the latest available quarter.
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset, "sort": sort}
        if category is not None:
            params["category"] = category
        if min_aum_usd is not None:
            params["minAumUsd"] = min_aum_usd
        if quarter is not None:
            params["quarter"] = quarter
        resp = self._get("/api/v1/institutional/institutions", params=params).json()
        return resp.get("data", resp)

    # ── Calendar endpoints ──────────────────────────────────────

    def get_earnings_calendar(
        self,
        ticker: Optional[str] = None,
        week: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        confirmed: Optional[bool] = None,
        time: Optional[str] = None,
    ) -> PreviewResult[EarningsCalendar]:
        """Get the upcoming earnings calendar.

        Auto-unwrapped. Access via ``result.earnings`` (list of events) and
        ``result.metadata``. Check ``result.is_preview``: a FREE key sees the
        current week, a PRO key sees the full forward window (about 30 days).
        Field richness is identical across tiers; the gate is the window.

        Args:
            ticker: Filter to a single ticker (e.g. ``"AAPL"``).
            week: Shorthand window: ``"this"`` or ``"next"``.
            date_from: Inclusive lower bound, ISO ``YYYY-MM-DD`` (overrides ``week``).
            date_to: Inclusive upper bound, ISO ``YYYY-MM-DD``.
            confirmed: When ``True``, only company-confirmed dates.
            time: Session filter: ``before_open``, ``after_close``,
                ``during_market``, or ``unknown``.
        """
        params: Dict[str, Any] = {}
        if ticker:
            params["ticker"] = ticker.upper()
        if week:
            params["week"] = week
        if date_from:
            params["from"] = date_from
        if date_to:
            params["to"] = date_to
        if confirmed is not None:
            params["confirmed"] = confirmed
        if time:
            params["time"] = time
        return self._unwrap(
            self._get("/api/v1/calendar/earnings", params=params).json(),
            item_cls=EarningsCalendar,
        )

    # ── Insider trading endpoints ───────────────────────────────

    def get_insider_activity(self, lookback_days: int = 90) -> PreviewResult[InsiderActivity]:
        """Get market-wide insider activity: top buys and sells aggregated by ticker.

        Auto-unwrapped. Access via ``result.buys`` and ``result.sells``.
        Check ``result.is_preview`` for tier status.

        Args:
            lookback_days: Number of days to look back (1-365). Default 90.
        """
        return self._unwrap(
            self._get("/api/v1/insider/activity", params={"lookbackDays": lookback_days}).json(),
            item_cls=InsiderActivity,
        )

    def get_insider_trades(self, ticker: str, lookback_days: int = 90) -> PreviewResult[List[InsiderTrade]]:
        """Get individual insider transactions for a specific stock.

        Auto-unwrapped. Iterate directly: ``for t in result: ...``.
        Check ``result.is_preview`` for tier status.

        Args:
            ticker: Stock ticker symbol (e.g., ``"AAPL"``).
            lookback_days: Number of days to look back (1-365). Default 90.
        """
        return self._unwrap(
            self._get(f"/api/v1/insider/trades/{ticker.upper()}", params={"lookbackDays": lookback_days}).json(),
            list_cls=InsiderTrade,
        )

    def get_insider_cluster_buys(self, lookback_days: int = 90) -> PreviewResult[List[ClusterBuy]]:
        """Get cluster buy signals: stocks where 3+ distinct insiders bought recently.

        Auto-unwrapped. Iterate directly: ``for c in result: ...``.
        Check ``result.is_preview`` for tier status.

        Args:
            lookback_days: Number of days to look back (1-365). Default 90.
        """
        return self._unwrap(
            self._get("/api/v1/insider/cluster-buys", params={"lookbackDays": lookback_days}).json(),
            list_cls=ClusterBuy,
        )

    # ── Politicians trading endpoints ──────────────────────────

    def get_politician_activity(self, lookback_days: int = 90) -> PreviewResult[List[CongressTrade]]:
        """Get recent congressional STOCK Act trading activity across all politicians.

        Auto-unwrapped. Iterate directly: ``for trade in result: ...``.
        Check ``result.is_preview`` for tier status.

        Args:
            lookback_days: Number of days to look back (1-365). Default 90.
        """
        return self._unwrap(
            self._get("/api/v1/politicians/activity", params={"lookbackDays": lookback_days}).json(),
            list_cls=CongressTrade,
        )

    def get_politician_filings(self, ticker: str, lookback_days: int = 90) -> PreviewResult[List[CongressTrade]]:
        """Get congressional trades for a specific stock.

        Auto-unwrapped. Iterate directly: ``for trade in result: ...``.
        Check ``result.is_preview`` for tier status.

        Args:
            ticker: Stock ticker symbol (e.g., ``"NVDA"``).
            lookback_days: Number of days to look back (1-365). Default 90.
        """
        return self._unwrap(
            self._get(f"/api/v1/politicians/filings/{ticker.upper()}", params={"lookbackDays": lookback_days}).json(),
            list_cls=CongressTrade,
        )

    def get_politician_members(self) -> PreviewResult[List[PoliticianSummary]]:
        """Get all tracked politicians with trading summary statistics.

        Auto-unwrapped. Iterate directly: ``for member in result: ...``.
        Check ``result.is_preview`` for tier status.
        """
        return self._unwrap(
            self._get("/api/v1/politicians/members").json(),
            list_cls=PoliticianSummary,
        )

    def get_politician_member(self, slug: str) -> PreviewResult[PoliticianDetail]:
        """Get detailed profile for a single politician.

        Auto-unwrapped. Access via ``result.profile``, ``result.recentTrades``,
        ``result.topTickers``. Check ``result.is_preview`` for tier status.

        Args:
            slug: Politician URL slug (e.g., ``"nancy-pelosi-house"``). Get slugs from ``get_politician_members()``.
        """
        return self._unwrap(
            self._get(f"/api/v1/politicians/member/{slug}").json(),
            item_cls=PoliticianDetail,
        )

    # ── Insights endpoints ──────────────────────────────────────

    def get_stock_insights(
        self,
        ticker: str,
        urgency: Optional[str] = None,
        insight_type: Optional[str] = None,
    ) -> PreviewResult[List[Insight]]:
        """Get AI-generated insights for a specific stock.

        Auto-unwrapped. Iterate directly: ``for i in result: ...``.
        Check ``result.is_preview`` for tier status.

        Args:
            ticker: Stock ticker symbol (e.g., ``"AAPL"``).
            urgency: Filter by urgency level: ``"low"``, ``"medium"``, or ``"high"``.
            insight_type: Filter by insight type (e.g., ``"insider_buy_signal"``).
        """
        params: Dict[str, Any] = {}
        if urgency:
            params["urgency"] = urgency
        if insight_type:
            params["insightType"] = insight_type
        return self._unwrap(
            self._get(f"/api/v1/insights/stock/{ticker.upper()}", params=params).json(),
            list_cls=Insight,
        )

    def get_market_insights(self) -> PreviewResult[List[Insight]]:
        """Get AI-generated market-level insights.

        Auto-unwrapped. Iterate directly: ``for i in result: ...``.
        Check ``result.is_preview`` for tier status.
        """
        return self._unwrap(
            self._get("/api/v1/insights/market").json(),
            list_cls=Insight,
        )

    def get_insight_types(self, ticker: str) -> List[str]:
        """Get available insight types for a specific stock.

        No authentication required. Returns a list of insight type strings
        such as ``"insider_buy_signal"``, ``"institutional_position_change"``, or ``"volume_anomaly_high"``.

        Args:
            ticker: Stock ticker symbol (e.g., ``"AAPL"``).
        """
        return self._get(f"/api/v1/insights/stock/{ticker.upper()}/types").json()

    def get_stock_insights_range(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        urgency: Optional[str] = None,
        insight_type: Optional[str] = None,
    ) -> PreviewResult[List[Insight]]:
        """Get AI insights for a stock within a date range.

        Auto-unwrapped. Check ``result.is_preview`` for tier status.

        Args:
            ticker: Stock ticker symbol.
            start_date: ISO date string ``"YYYY-MM-DD"`` (inclusive).
            end_date: ISO date string ``"YYYY-MM-DD"`` (inclusive, on or after ``start_date``).
            urgency: Optional urgency filter (``"low"``, ``"medium"``, ``"high"``).
            insight_type: Optional insight type filter.
        """
        params: Dict[str, Any] = {"startDate": start_date, "endDate": end_date}
        if urgency:
            params["urgency"] = urgency
        if insight_type:
            params["insightType"] = insight_type
        return self._unwrap(
            self._get(f"/api/v1/insights/stock/{ticker.upper()}/range", params=params).json(),
            list_cls=Insight,
        )

    def get_latest_insights(
        self,
        limit: int = 50,
        urgency: Optional[str] = None,
    ) -> PreviewResult[List[Insight]]:
        """Get the latest AI insights across all tracked stocks, newest first.

        Auto-unwrapped. Free users receive the top 5; PRO users receive up to ``limit``.

        Args:
            limit: Max insights to return. Server clamps to the range 1-200.
            urgency: Optional urgency filter.
        """
        params: Dict[str, Any] = {"limit": limit}
        if urgency:
            params["urgency"] = urgency
        return self._unwrap(
            self._get("/api/v1/insights/latest", params=params).json(),
            list_cls=Insight,
        )

    def get_user_insights(
        self,
        limit: int = 20,
        category: Optional[str] = None,
    ) -> PreviewResult[List[Insight]]:
        """Get personalized insights for the authenticated user.

        Biased toward the user's watchlist and portfolio when available; falls
        back to market-level insights otherwise. API key authentication required.

        Args:
            limit: Max insights to return. Server clamps to the range 1-100.
            category: Optional category filter (``"SENTIMENT"``, ``"INSIDER"``, ``"INSTITUTIONAL"``, etc.).
        """
        params: Dict[str, Any] = {"limit": limit}
        if category:
            params["category"] = category
        return self._unwrap(
            self._get("/api/v1/insights/user", params=params).json(),
            list_cls=Insight,
        )

    # ── Analyst Ratings endpoints ───────────────────────────────

    def get_analyst_consensus(self, ticker: str) -> PreviewResult[Dict[str, Any]]:
        """Get the aggregate Wall Street consensus for a ticker.

        PRO users receive the full buy/hold/sell distribution; free users receive
        the price target band (``targetLow``, ``targetMean``, ``targetHigh``,
        ``numberOfAnalysts``, ``consensusLabel``) but the distribution counts
        are zeroed out.

        Args:
            ticker: Stock ticker symbol (e.g. ``"AAPL"``).
        """
        return self._unwrap(
            self._get(f"/api/v1/analyst/{ticker.upper()}/consensus").json(),
        )

    def get_analyst_actions(
        self,
        ticker: str,
        lookback_days: int = 90,
    ) -> PreviewResult[List[Dict[str, Any]]]:
        """Get recent analyst upgrade/downgrade actions for a ticker, newest first.

        Free users receive the 3 most recent actions; PRO users receive the full list.

        Args:
            ticker: Stock ticker symbol.
            lookback_days: Days of history to return (default 90).
        """
        return self._unwrap(
            self._get(
                f"/api/v1/analyst/{ticker.upper()}/actions",
                params={"lookbackDays": lookback_days},
            ).json(),
        )

    def get_analyst_estimates(self, ticker: str) -> PreviewResult[Dict[str, Any]]:
        """Get forward EPS estimates and earnings surprise history for a ticker.

        Free users receive 1 estimate (current quarter) plus the 2 most recent
        surprises; PRO users receive the full history.

        Args:
            ticker: Stock ticker symbol.
        """
        return self._unwrap(
            self._get(f"/api/v1/analyst/{ticker.upper()}/estimates").json(),
        )

    def get_analyst_market_activity(
        self,
        lookback_days: int = 30,
    ) -> PreviewResult[List[Dict[str, Any]]]:
        """Get market-wide recent analyst actions across all covered tickers.

        Free users receive the 5 most recent actions; PRO users receive the full list.

        Args:
            lookback_days: Days of history to return (default 30).
        """
        return self._unwrap(
            self._get(
                "/api/v1/analyst/activity",
                params={"lookbackDays": lookback_days},
            ).json(),
        )

    # ── Knowledge Base (KB) endpoints ───────────────────────────

    def get_popular_kb_entities(self) -> List[Dict[str, Any]]:
        """Get popular KB entities (useful for search suggestions)."""
        return self._get("/api/v1/kb/entities/popular").json()

    # ── ETF endpoints ───────────────────────────────────────────

    def list_etfs(self) -> List[EtfInfo]:
        """List every ETF tracked by SentiSense.

        Sorted by ticker. Each entry includes ticker, fund name, KB entity ID,
        URL slug, issuer, tracked index, and asset class.

        Auth: API key required (no quota cost).
        """
        return self._parse_list(self._get("/api/v1/etfs").json(), EtfInfo)

    def get_etf_holdings(self, ticker: str) -> EtfHoldings:
        """Return the full holdings composition for an ETF.

        Includes per-holding weights and freshness metadata (``as_of_date``,
        ``fetched_at``, ``next_refresh_due``). When the composition is a
        top-N view (e.g. via a third-party aggregator), ``partial`` is true
        and ``total_known_holdings`` reflects the issuer's true count.

        Args:
            ticker: ETF ticker (e.g. ``"QQQ"``).
        """
        return EtfHoldings.from_dict(
            self._get(f"/api/v1/etfs/{ticker.upper()}/holdings").json()
        )

    def get_etf_analyst_aggregate(self, ticker: str) -> PreviewResult[EtfAnalystAggregate]:
        """Get the holdings-weighted analyst consensus for an ETF.

        Synthesized from each constituent's per-stock analyst coverage,
        weighted by allocation and renormalized to the covered subset.
        Free users receive the headline and coverage block; PRO unlocks
        the per-holding ``topContributors`` array.

        Args:
            ticker: ETF ticker.
        """
        return self._unwrap(
            self._get(f"/api/v1/etfs/{ticker.upper()}/aggregates/analyst").json(),
            item_cls=EtfAnalystAggregate,
        )

    def get_etf_insider_aggregate(
        self,
        ticker: str,
        lookback_days: int = 30,
    ) -> PreviewResult[EtfInsiderAggregate]:
        """Get the holdings-weighted SEC Form 4 insider aggregate for an ETF.

        Returns net dollar flow, gross buy/sell amounts, and trade counts
        across the fund's constituents over the trailing window. Free users
        receive the headline + buy/sell split; PRO unlocks per-holding
        ``topContributors`` with signed contribution.

        Args:
            ticker: ETF ticker.
            lookback_days: Trailing window for the trade aggregation (default 30,
                upper-bound clamp at 90).
        """
        return self._unwrap(
            self._get(
                f"/api/v1/etfs/{ticker.upper()}/aggregates/insider",
                params={"lookbackDays": lookback_days},
            ).json(),
            item_cls=EtfInsiderAggregate,
        )

    def get_etf_sentiment_aggregate(self, ticker: str) -> PreviewResult[EtfSentimentAggregate]:
        """Get two SentiSense Score readings for an ETF side-by-side.

        **Beta** as of 2026-05-15: the constituent-weighted score is being
        produced for a limited starter set of funds. Expect 404 for funds
        outside the current coverage window; re-check daily.

        Returns ``constituentsWeighted`` (precomputed weighted score across
        the fund's holdings) and ``direct`` (score from mentions of the
        fund's own ticker). These can diverge meaningfully and the gap is
        itself information. ``direct`` may be ``None`` for low-mention funds.

        Args:
            ticker: ETF ticker.
        """
        return self._unwrap(
            self._get(f"/api/v1/etfs/{ticker.upper()}/aggregates/sentiment").json(),
            item_cls=EtfSentimentAggregate,
        )

    # ── Company KPIs endpoint ───────────────────────────────────

    def get_company_kpis(self, ticker: str) -> PreviewResult[CompanyKpis]:
        """Get company-specific KPI time-series for a ticker.

        Curated GAAP and non-GAAP metrics from earnings filings (e.g. iPhone unit
        sales, Tesla deliveries, AWS revenue). Free users receive metadata only
        with an empty ``kpis`` list; PRO users receive the full series. Returns
        404 for tickers that do not yet have curated coverage.

        Coverage today: near-complete for the S&P 500 plus extended universe
        (~500 tickers). Use :meth:`list_kpi_coverage` to enumerate.

        Args:
            ticker: Stock ticker symbol.
        """
        return self._unwrap(
            self._get(f"/api/v1/stocks/{ticker.upper()}/kpis").json(),
            item_cls=CompanyKpis,
        )

    def list_kpi_coverage(self) -> KpiCoverage:
        """List every ticker with curated KPI coverage.

        Returns a typed :class:`KpiCoverage` envelope: ``count`` plus the list
        of :class:`KpiCoverageEntry` (ticker, companyName, lastUpdated, kpiCount).
        Sorted alphabetically by ticker. Use this to discover what's available
        before calling :meth:`get_company_kpis` per ticker.

        Auth: API key required, but the call does NOT consume your monthly
        quota (rate-limit-per-minute still applies).
        """
        data = self._get("/api/v1/stocks/with-kpis").json()
        return KpiCoverage.from_dict(data)

    def get_kpi_types(self, ticker: str) -> List[KpiTypeEntry]:
        """List the KPI metadata tuples available for a ticker.

        Returns a list of :class:`KpiTypeEntry` (id, name, category, chartType)
        without paying the cost of the full series payload. Mirrors the
        ``/api/v1/insights/stock/{ticker}/types`` precedent. Useful for letting
        an agent or UI decide which KPIs to render before fetching the data.

        Auth: API key required, no quota cost. 404 if the ticker has no
        curated KPIs.

        Args:
            ticker: Stock ticker symbol.
        """
        data = self._get(f"/api/v1/stocks/{ticker.upper()}/kpis/types").json()
        return [KpiTypeEntry.from_dict(t) for t in (data or [])]

    # ── Fundamentals endpoint ───────────────────────────────────

    def get_fundamentals_periods(
        self, ticker: str, timeframe: Optional[str] = None
    ) -> List[FundamentalsPeriod]:
        """List available SEC reporting periods for a ticker, with fiscal labels.

        Returns the catalog of recent reporting periods, each carrying the
        authoritative ``fiscalPeriod`` (Q1..Q4 / FY), ``fiscalYear``, and
        ``periodEndDate`` as filed with the SEC. Useful for driving a period
        picker, or for mapping a period-end date to its fiscal quarter/year.

        By default returns every period (quarterly and annual), matching the Node
        SDK's ``getFundamentalsPeriods``. Pass ``timeframe="quarterly"`` or
        ``"annual"`` to filter client-side. Returns an empty list for tickers with
        no SEC filings (recent listings, ETFs/funds).

        Args:
            ticker: Stock ticker symbol.
            timeframe: ``None`` (default, all periods), ``"quarterly"``, or ``"annual"``.
        """
        data = self._get(
            "/api/v1/stocks/fundamentals/periods", params={"ticker": ticker.upper()}
        ).json()
        periods = [FundamentalsPeriod.from_dict(p) for p in (data.get("periods") or [])]
        if timeframe:
            periods = [
                p for p in periods if (p.timeframe or "").lower() == timeframe.lower()
            ]
        return periods

    # ── Market Mood endpoint ────────────────────────────────────

    def get_market_mood(self, days: int = 180) -> Dict[str, Any]:
        """Get the SentiSense Market Mood composite (fear/greed index).

        Returns the latest score, daily history, per-signal breakdown, and
        per-sector summaries. Free for all users; no API key required (though
        an API key counts the call against your monthly quota if supplied).

        Note: lives at ``/api/v2/market-mood`` (v2 path, not v1).

        Args:
            days: Days of history to return (default 180).
        """
        return self._get("/api/v2/market-mood", params={"days": days}).json()

    # ── Document & news endpoints ───────────────────────────────

    def get_documents_by_ticker(
        self,
        ticker: str,
        source: Optional[str] = None,
        days: Optional[int] = None,
        hours: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> DocumentSearchResponse:
        """Get document metrics for a stock ticker.

        Args:
            ticker: Stock ticker symbol.
            source: Filter by source: "news", "reddit", "x", "substack", or "youtube".
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
        return self._parse(self._get(f"/api/v1/documents/ticker/{ticker}", params=params).json(), DocumentSearchResponse)

    def get_documents_by_ticker_range(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        source: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> DocumentSearchResponse:
        """Get news articles for a stock within a date range.

        Args:
            ticker: Stock ticker symbol.
            start_date: Start date (e.g. "2025-01-01").
            end_date: End date (e.g. "2025-01-31").
            source: Filter by source — "news", "reddit", "x", "substack", or "youtube".
            limit: Maximum number of results.
        """
        params: Dict[str, Any] = {"startDate": start_date, "endDate": end_date}
        if source:
            params["source"] = source
        if limit is not None:
            params["limit"] = limit
        return self._parse(self._get(f"/api/v1/documents/ticker/{ticker}/range", params=params).json(), DocumentSearchResponse)

    def get_documents_by_entity(
        self,
        entity_id: str,
        source: Optional[str] = None,
        days: Optional[int] = None,
        hours: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> DocumentSearchResponse:
        """Get documents for a knowledge base entity.

        Args:
            entity_id: KB entity ID.
            source: Filter by source — "news", "reddit", "x", "substack", or "youtube".
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
        return self._parse(self._get(f"/api/v1/documents/entity/{entity_id}", params=params).json(), DocumentSearchResponse)

    def search_documents(
        self,
        query: str,
        source: Optional[str] = None,
        days: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> DocumentSearchResponse:
        """Search news and social posts with a natural language query.

        Args:
            query: Search query string.
            source: Filter by source — "news", "reddit", "x", "substack", or "youtube".
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
        return self._parse(self._get("/api/v1/documents/search", params=params).json(), DocumentSearchResponse)

    def get_documents_by_source(
        self,
        source: str,
        days: Optional[int] = None,
        hours: Optional[int] = None,
        limit: Optional[int] = None,
        sort: Optional[str] = None,
    ) -> DocumentSearchResponse:
        """Get latest documents from a specific source.

        Args:
            source: Source type — "news", "reddit", "x", "substack", or "youtube".
            days: Look back N days.
            hours: Look back N hours.
            limit: Maximum number of results.
            sort: Result ordering. "latest" (default) returns newest first.
                "top" returns a reliability-first ranking that surfaces recent
                content from high-authority publishers ahead of low-authority
                floods.
        """
        params: Dict[str, Any] = {}
        if days is not None:
            params["days"] = days
        if hours is not None:
            params["hours"] = hours
        if limit is not None:
            params["limit"] = limit
        if sort is not None:
            params["sort"] = sort
        return self._parse(self._get(f"/api/v1/documents/source/{source}", params=params).json(), DocumentSearchResponse)

    def get_stories(
        self,
        limit: Optional[int] = None,
        days: Optional[int] = None,
        offset: Optional[int] = None,
        filter_hours: Optional[int] = None,
    ) -> List[Story]:
        """Get AI-curated news story clusters.

        Returns story objects with title, sentiment, impact score, and tickers.
        Each story includes a ``brokeAt`` field (epoch seconds, nullable when
        no representative document timestamp is available).

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
        return self._parse_list(self._get("/api/v1/documents/stories", params=params).json(), Story)

    def get_stories_by_ticker(self, ticker: str, limit: Optional[int] = None) -> List[Story]:
        """Get news stories for a specific stock.

        Args:
            ticker: Stock ticker symbol.
            limit: Maximum number of stories.
        """
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        return self._parse_list(self._get(f"/api/v1/documents/stories/ticker/{ticker}", params=params).json(), Story)

    # ── Market summary endpoint ────────────────────────────────

    def get_market_summary(self) -> MarketSummary:
        """Get the AI-generated market summary."""
        return self._parse(self._get("/api/v1/market-summary").json(), MarketSummary)

    # ── Metrics endpoints (v2) ──────────────────────────────────

    def get_metrics(
        self,
        symbol: str,
        metric_type: str = "sentiment",
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

        Returns:
            A list of points, time-ordered ascending by ``timestamp``. Each point
            carries a flat ``value`` scalar (the polarity for sentiment, the count for
            mentions); read that instead of walking the nested ``metricValue.value``
            (count metrics) or ``metricValue.value.value`` (value metrics). A point
            with no reading omits ``value``. For the current reading and its change,
            take the last point's ``value`` and subtract the prior point's; a window
            with 0 or 1 point has no derivable trend, so widen ``start_time``.
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

    def list_trackers(self) -> TrackerListResponse:
        """List every publicly-visible tracker.

        Returns a discovery envelope with one ``TrackerListing`` per tracker:
        id, display name, category, one-line description, viewType (the
        renderer hint), and the methodology anchor to link out to.
        """
        return TrackerListResponse.from_dict(self._get("/api/v1/trackers").json())

    def get_tracker(
        self,
        tracker_id: str,
        **params: Any,
    ) -> PreviewResult:
        """Return the standardized snapshot envelope for one tracker.

        The wire response is the unified preview envelope
        ``{isPreview, previewReason, totalCount?, data: TrackerSnapshot}``;
        the SDK wraps it as a :class:`PreviewResult` so you can:
        ``snapshot = client.get_tracker("institution-concentration")``,
        then read ``snapshot.is_preview``, ``snapshot.total_count``, and
        ``snapshot.data`` (a :class:`TrackerSnapshot`).

        Dispatch on ``snapshot.data.viewType`` to pick a renderer.
        ``"table"`` rows live at ``snapshot.data.rows``; ``"choropleth"``
        regions live at ``snapshot.data.geo``; etc.

        Args:
            tracker_id: Slug from :meth:`list_trackers`, e.g.
                ``"institution-concentration"``.
            **params: Provider-specific query parameters (e.g. ``scope="us"``
                for geographically-scoped trackers like hantavirus). Unknown
                keys are ignored.
        """
        body = self._get(f"/api/v1/trackers/{tracker_id}", params=params).json()
        return self._unwrap(body, item_cls=TrackerSnapshot)
