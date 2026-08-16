"""SentiSense API client."""

import math
import random
import time
from typing import Any, Dict, List, Literal, Optional, Type, TypeVar

import requests

from sentisense.__about__ import __version__
from sentisense.exceptions import DeepHistoryUnavailable, SentiSenseError, _raise_for_status
from sentisense.types import (
    APIModel,
    ClusterBuy,
    CompanyKpis,
    CongressTrade,
    Document,
    EarningsCalendar,
    EarningsQuarter,
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
    EtfScreenerResults,
    FeaturedScreen,
    PoliticianDetail,
    PoliticianSummary,
    PreviewResult,
    Quarter,
    RecentEarningsEntry,
    ScreenerFieldCatalog,
    ScreenerResults,
    SimilarStock,
    StockDetail,
    StockPrice,
    StockQuote,
    Story,
    IndexHistoryResponse,
    IndexListResponse,
    IndexSnapshot,
    TrackerListResponse,
    TrackerSnapshot,
)

_M = TypeVar("_M", bound=APIModel)


# Deep chart ranges ("10Y", "MAX") answer 202 while a cold stock's history is assembled.
# Retries are bounded: if the upstream is throttled the series will not arrive within any
# reasonable wait, and blocking a caller indefinitely is worse than raising.
_DEEP_HISTORY_ATTEMPTS = 3
_DEEP_HISTORY_FALLBACK_WAIT = 3.0

# Upper bounds on any server-supplied Retry-After. This client is synchronous, so the wait
# blocks the calling thread for its whole duration; without a ceiling a single oversized
# header value turns into an unbounded hang that looks like the process is wedged. Rate
# limiting gets the longer ceiling because a genuine limit window is legitimately minutes.
_MAX_DEEP_HISTORY_WAIT = 30.0
_MAX_RATE_LIMIT_WAIT = 120.0
_RATE_LIMIT_FALLBACK_WAIT = 60.0


def _retry_after_seconds(
    response: "requests.Response",
    default: float = _DEEP_HISTORY_FALLBACK_WAIT,
    max_wait: float = _MAX_DEEP_HISTORY_WAIT,
) -> float:
    """Seconds to wait before retrying, from ``Retry-After`` when present.

    The result is clamped to ``[0.5, max_wait]``. ``Retry-After`` may legally carry an
    HTTP-date instead of a number of seconds, and ``float()`` also accepts ``"nan"`` and
    ``"inf"``, so anything that is not a finite number falls back to ``default`` rather
    than raising or producing a nonsense sleep.
    """
    raw = response.headers.get("Retry-After")
    if not raw:
        return default
    try:
        seconds = float(raw)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(seconds):
        return default
    return min(max(0.5, seconds), max_wait)


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
                    delay = _retry_after_seconds(
                        resp,
                        default=_RATE_LIMIT_FALLBACK_WAIT,
                        max_wait=_MAX_RATE_LIMIT_WAIT,
                    )
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
        after-hours, the response includes a nested ``extendedHours`` object; see
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
        """Get company profile for a stock.

        A stock that has stopped trading, or is scheduled to, also carries
        ``listingStatus``, ``delistedDate`` and ``delistingReason``; see
        :class:`~sentisense.types.StockPrice` for what those values mean.
        """
        return self._get(f"/api/v1/stocks/{ticker}/profile").json()

    def get_stock_sentiment(self, ticker: str) -> PreviewResult[Dict[str, Any]]:
        """Get the headline sentiment picture for a stock in one call.

        Returns the SentiSense Score with its 30-day regime (``sentisenseScore``,
        ``sentisenseScoreAvg30d``, ``sentisenseScoreDelta30d``, ``scoreLabel``,
        ``direction``, ``latestDirection``, ``trend``, ``scoreSparkline``), mention
        volume (``mentions``, ``mentionsAvg30d``, and ``socialDominance`` as a
        fraction where ``0.021`` means 2.1%), per-source tone in ``bySource``
        (``source``, ``direction``, ``mentionShare``, and ``value`` for the exact
        polarity in ``[-1, 1]``), plus ``relatedTickers``, ``drivers``, ``narrative``
        and ``faq``.

        ``mentionShare`` is a whole-number percent of the ticker's mentions, rounded
        per source. Each source's share is rounded independently, so the list sums to
        about 100 rather than exactly 100: 101 is common and is not a data error. Do
        not use the shares to reconstruct per-source counts.

        Note that ``mentionShare`` and ``socialDominance`` are in different units: the
        first is a percent, the second a fraction.

        Auto-unwrapped. Available in full on every API-key tier.

        Use :meth:`get_metrics` with ``metric_type="sentiment"`` instead when you
        need a time series over a specific window rather than the headline read.

        Args:
            ticker: Stock ticker symbol (e.g., ``"AAPL"``).

        Raises:
            NotFoundError: The ticker has no sentiment coverage.
        """
        return self._unwrap(
            self._get(f"/api/v1/stocks/{ticker}/sentiment").json(),
        )

    def get_stock_entities(self, ticker: str) -> List[Dict[str, Any]]:
        """Get the tracked entities related to a stock (executives, products, organizations).

        Each entry carries ``id`` (the knowledge-base id, e.g. ``"kb/person/1"``),
        ``displayName``, ``type`` ("PERSON", "PRODUCT", ...), ``relatedStock``,
        ``urlSlug``, and the nullable ``title``, ``category`` and ``iconUrl``.
        Pass ``urlSlug`` to :meth:`get_metrics` to pull an entity's time series.

        Args:
            ticker: Stock ticker symbol (e.g., ``"AAPL"``).
        """
        return self._get(f"/api/v1/stocks/{ticker}/entities").json()

    def get_stock_ai_summary(self, ticker: str, depth: str = "basic") -> Dict[str, Any]:
        """Get the curated AI research report for a stock.

        Returns a flat object, not a preview envelope: ``ticker``, ``companyName``,
        ``status`` ("READY", "NOT_AVAILABLE" or "ERROR"), ``statusReason`` (set on the
        latter two only), ``reportType``, ``version`` (the report date encoded as a
        ``yymmdd`` integer, e.g. ``260520``), ``lastUpdated`` (epoch **milliseconds**,
        not seconds like the timestamps elsewhere in this SDK), ``sections`` (a map of
        section name to ``{"content": ..., "directives": [...]}``) and ``sectionOrder``.

        Both depths return ``sections`` and ``sectionOrder``, so their presence does not
        tell you which report you got. Read ``reportType`` instead: ``"SUMMARY"`` for
        ``depth="basic"``, ``"FULL"`` for ``depth="deep"``.

        ``depth="deep"`` additionally carries ``moatRating`` (0 to 10, ``None`` if the
        ticker has not been assessed) and ``aiDisruptionRisk`` ("Low", "Medium", "High"
        or "Critical", likewise nullable). It consumes one report view per call on
        metered tiers; ``depth="basic"`` does not.

        A ticker with no published report answers ``200`` with ``status`` of
        ``"NOT_AVAILABLE"`` rather than raising, so branch on ``status`` before reading
        ``sections``.

        Args:
            ticker: Stock ticker symbol (e.g., ``"AAPL"``).
            depth: ``"basic"`` for the one-paragraph summary (default), or ``"deep"``
                for the full report.

        Raises:
            RateLimitError: The account's monthly report views are exhausted. This
                shares the ``429`` status with per-minute rate limiting, which the
                client retries, so an exhausted monthly allowance waits out
                ``max_retries`` backoffs before raising. Pass ``max_retries=0`` when
                calling ``depth="deep"`` in a loop if you would rather fail fast.
        """
        return self._get(
            f"/api/v1/stocks/{ticker}/ai-summary",
            params={"depth": depth},
        ).json()

    def get_similar_stocks(self, ticker: str, limit: int = 5) -> List[SimilarStock]:
        """Get peer/similar stocks with current prices.

        Args:
            ticker: Stock ticker symbol (e.g., ``"AAPL"``).
            limit: Maximum number of results (default 5).
        """
        return self._parse_list(self._get(f"/api/v1/stocks/{ticker}/similar", params={"limit": limit}).json(), SimilarStock)

    def get_stock_chart(self, ticker: str, timeframe: str = "1M") -> List[Dict[str, Any]]:
        """Get OHLCV chart data for a stock.

        Returns a bare list of bars, oldest first. There is no wrapper object, so
        index it (``bars[-1]["close"]``) or iterate it; do not subscript it by
        field name.

        Args:
            ticker: Stock ticker symbol.
            timeframe: Chart timeframe. One of "1D", "5D", "1W", "1M", "3M", "6M",
                "1Y", "5Y", "10Y", "MAX". "MAX" returns the full available history
                (up to ~26 years). "10Y" and "MAX" are split- and dividend-adjusted;
                every shorter range, "5Y" included, is split-adjusted only, so the
                same historical day can carry a different close depending on which
                timeframe you asked for. "ALL" is a legacy alias of "5Y" and still
                accepted.

        Each bar carries: ``timestamp`` (Unix ms), ``date`` (display string), ``open``,
        ``high``, ``low``, ``close``, ``volume``, and ``session`` ("pre" / "regular" /
        "post" for intraday timeframes; ``None`` for daily and weekly bars).

        The deep ranges ("10Y", "MAX") answer ``202`` while a rarely-requested stock's
        history is still being assembled. This method retries that automatically,
        honouring ``Retry-After``, and raises :class:`DeepHistoryUnavailable` if the
        series is still not ready. It never returns a shorter range in place of the one
        you asked for, so a successful call always carries the requested timeframe.
        """
        for attempt in range(_DEEP_HISTORY_ATTEMPTS):
            response = self._get(
                "/api/v1/stocks/chart",
                params={"ticker": ticker, "timeframe": timeframe},
            )
            if response.status_code != 202:
                return response.json()
            if attempt == _DEEP_HISTORY_ATTEMPTS - 1:
                break
            time.sleep(_retry_after_seconds(response))
        raise DeepHistoryUnavailable(
            f"Deep history for {ticker} ({timeframe}) is still being assembled. "
            "Retry in a few seconds."
        )

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

        Returns one reporting period: income statement, balance sheet, and cash
        flow line items, keyed camelCase as on the wire.

        Currency: figures are **as reported in the filer's own currency**, never
        converted to US dollars. Foreign companies listed as ADRs file in their
        home currency (KRW, JPY, EUR, ...) while their listed share price is in
        USD. The optional ``reportedCurrency`` key ("USD", "KRW", ...) names the
        currency; when absent it is unknown, not implicitly USD. For non-USD
        filers the API serves ``peRatio`` / ``psRatio`` / ``pbRatio`` as ``None``
        on purpose (a USD price over a home-currency per-share figure is a unit
        mismatch); do not recompute them client-side.

        Cash-flow keys worth knowing, since their signs and relationships are
        easy to get wrong:

        - ``operatingCashFlow`` / ``investingCashFlow`` / ``financingCashFlow``:
          net cash from each activity, in the reporting currency.
        - ``capitalExpenditure``: in the reporting currency, signed **as filed**, so normally
          NEGATIVE because it is an outflow. Take ``abs()`` before using it as a
          magnitude.
        - ``freeCashFlow``: ``operatingCashFlow - abs(capitalExpenditure)``. It is
          ``None`` rather than a guess when the period's capital expenditure is
          unavailable, so a screen for positive free cash flow can never match on
          a fabricated number. Do not substitute
          ``operatingCashFlow + investingCashFlow``: investing cash flow also
          carries marketable-securities and acquisition activity, which for a
          company holding a large securities portfolio is wrong by billions and
          can flip the sign.

        Args:
            ticker: Stock ticker symbol.
            timeframe: "quarterly" or "annual".
            fiscal_period: Filter by fiscal period (e.g. "Q1", "Q2").
            fiscal_year: Filter by fiscal year (e.g. 2025).

        Example:
            >>> q = client.get_fundamentals("AAPL")
            >>> abs(q["capitalExpenditure"]), q["freeCashFlow"]
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

    def get_stock_holders(
        self,
        ticker: str,
        report_date: str,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        sort_by: Optional[Literal["shares", "valueUsd", "sharesChangePct"]] = None,
        sort_dir: Optional[Literal["asc", "desc"]] = None,
    ) -> PreviewResult:
        """Get institutional holders for a specific stock.

        Auto-unwrapped. Check ``result.is_preview`` for tier status.

        A widely held ticker returns thousands of rows: a megacap quarter is about
        6,000 holders and 1.5 MB. Pass ``limit`` unless you really want all of them.
        Omitting every paging argument sends the original unbounded request.

        Paged responses also carry ``returnedCount`` and ``offset`` alongside the
        holder rows, so you can walk the list without re-counting it yourself.

        Args:
            ticker: Stock ticker symbol.
            report_date: Quarter date string (e.g. "2025-12-31").
            limit: Maximum holder rows to return. Must be >= 1; values above 1000
                are capped server-side. Omit for the full list.
            offset: Row offset to start from, for paging with ``limit``. Server
                default is 0.
            sort_by: Sort field, one of "shares" (server default), "valueUsd", or
                "sharesChangePct".
            sort_dir: Sort direction, "desc" (server default) or "asc".
        """
        params: Dict[str, Any] = {"reportDate": report_date}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if sort_by is not None:
            params["sortBy"] = sort_by
        if sort_dir is not None:
            params["sortDir"] = sort_dir
        return self._unwrap(
            self._get(f"/api/v1/institutional/holders/{ticker}", params=params).json(),
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

    # ── Earnings analysis report endpoints ──────────────────────

    def get_earnings_summaries(
        self, ticker: str, limit: Optional[int] = None
    ) -> PreviewResult[List[EarningsQuarter]]:
        """Get the per-quarter earnings analysis report for a ticker, newest first.

        One :class:`EarningsQuarter` per fiscal quarter, carrying the editorial
        headline, the KPI cards that matter for that company with year-over-year
        deltas, the guidance language as management phrased it, and a summary of
        the earnings call.

        Auto-unwrapped: iterate ``result`` or read ``result.data``. Check
        ``result.is_preview``. A PRO key receives every hydrated quarter in
        full; a FREE key receives the latest quarter shaped rather than
        truncated, plus ``result.total_count``. See :class:`EarningsQuarter`
        for which fields each tier carries.

        A quarter typically appears within 48 hours of the company reporting,
        and the call summary can arrive after the press-release content for the
        same quarter, so read ``generatedAt`` and ``transcriptGeneratedAt``
        rather than assuming a fixed lag. A ticker with no stored quarter
        answers with an empty list, not a 404.

        Args:
            ticker: Stock ticker symbol, canonical form (``"GOOGL"``, not
                ``"GOOG"``; ``"BRK.B"``, not ``"BRK-B"``).
            limit: Max quarters returned, 1 to 40. Omitted, the API applies
                its own default of 12. FREE keys receive one quarter whatever
                you pass.
        """
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        return self._unwrap(
            self._get(
                f"/api/v1/stocks/{ticker.upper()}/earnings-summaries", params=params
            ).json(),
            list_cls=EarningsQuarter,
        )

    def get_recent_earnings(
        self, days: Optional[int] = None, limit: Optional[int] = None
    ) -> PreviewResult[List[RecentEarningsEntry]]:
        """Get the companies that reported in a recent window, newest first.

        The cross-ticker view: use it to drive a post-earnings sweep ("who
        reported this week"), then follow up per ticker with
        :meth:`get_earnings_summaries`.

        Auto-unwrapped: iterate ``result`` or read ``result.data``. Every API
        key receives the full window it asks for, so ``result.is_preview`` is
        always ``False`` here.

        The window is bounded by ``reportDate``, so a quarter reported inside
        it appears even when its call summary lands later. An empty list means
        nobody in the covered set reported in that window, not an error. This
        is the backward-looking feed; :meth:`get_earnings_calendar` is the
        forward-looking one.

        Args:
            days: Look-back window in days, 1 to 31. Omitted, the API applies
                its own default of 7.
            limit: Max rows returned, 1 to 100. Omitted, the API applies its
                own default of 50.
        """
        params: Dict[str, Any] = {}
        if days is not None:
            params["days"] = days
        if limit is not None:
            params["limit"] = limit
        return self._unwrap(
            self._get("/api/v1/earnings/recent", params=params).json(),
            list_cls=RecentEarningsEntry,
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

    def get_politician_activity(
        self,
        lookback_days: int = 90,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> PreviewResult[List[CongressTrade]]:
        """Get recent congressional STOCK Act trading activity across all politicians.

        Auto-unwrapped. Iterate directly: ``for trade in result: ...``.
        Check ``result.is_preview`` for tier status.

        The window holds far more rows than one response returns. A 365-day lookback
        covers thousands of trades but answers with the first page only, so read
        ``result.total_count`` to size the window and page through it with ``limit``
        and ``offset``. Omitting both sends the original unpaged request.

        Args:
            lookback_days: Number of days to look back (1-365). Default 90.
            limit: Maximum rows to return. Values above the server cap are clamped
                server-side. Omit for the server's own default page size.
            offset: Row offset to start from, for paging with ``limit``. Server
                default is 0.

        Example::

            first = client.get_politician_activity(lookback_days=365, limit=500)
            print(first.total_count)
            more = client.get_politician_activity(
                lookback_days=365, limit=500, offset=500
            )
        """
        params: Dict[str, Any] = {"lookbackDays": lookback_days}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return self._unwrap(
            self._get("/api/v1/politicians/activity", params=params).json(),
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

        API key required. Returns a list of insight type strings
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
        per-sector summaries. Available on every tier; send your API key on
        every call. Requests count against your monthly quota.

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
            source: Filter by source: "news", "reddit", "x", "substack", or "youtube".
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
            source: Filter by source: "news", "reddit", "x", "substack", or "youtube".
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
            source: Source type: "news", "reddit", "x", "substack", or "youtube".
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
        """Get time series metrics for a stock or entity (mentions, sentiment, etc.).

        Args:
            symbol: Stock ticker symbol (e.g. "AAPL") or entity urlSlug
                (e.g. "Nancy-Pelosi"). Case-insensitive. Discover slugs via
                ``GET /api/v1/kb/entities/search?q=`` or ``get_stock_entities()``.
            metric_type: Metric to retrieve: "mentions", "sentiment",
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
            metric_type: Metric to retrieve: "mentions", "sentiment",
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

    # ── Entity metrics endpoints (DEPRECATED: use get_metrics / get_metrics_distribution) ──

    # ── Indexes ──────────────────────────────────────────────────

    def list_indexes(self) -> IndexListResponse:
        """List every index the platform publishes.

        Returns a discovery envelope with one :class:`IndexListing` per index:
        id, display name, one-line description, the scale it lives on, its
        access tier, and where its richest view lives.

        Iterate this rather than hardcoding ids. Every ``indexId`` it advertises
        resolves on :meth:`get_index` and :meth:`get_index_history`.
        """
        return IndexListResponse.from_dict(self._get("/api/v1/indexes").json())

    def get_index(self, index_id: str) -> IndexSnapshot:
        """Return the latest reading for one index.

        Two archetypes share one envelope. A basket index (``fed-sentiment``,
        ``ai-sentiment``) populates ``constituents``, ``basketSize``,
        ``coverage`` and ``totalMentions``; a composite index (``market-mood``)
        returns ``None`` for all four *by construction*, because it is built
        from signals rather than entities. Check for ``None`` before iterating
        ``constituents``.

        For Market Mood specifically, this is the narrowed view. The phase band,
        weekly change, per-signal breakdown and per-sector map live on
        :meth:`get_market_mood`, and both report the same headline number.

        Args:
            index_id: Slug from :meth:`list_indexes`, e.g. ``"fed-sentiment"``.
        """
        return IndexSnapshot.from_dict(self._get(f"/api/v1/indexes/{index_id}").json())

    def get_index_history(self, index_id: str, days: int = 180) -> IndexHistoryResponse:
        """Return an index's historical scalar series, for charting.

        Point spacing follows the index rather than the calendar, and thin or
        low-coverage buckets are withheld, so the series can be shorter than
        ``days`` and can contain gaps. Plot against each point's ``date``.

        Args:
            index_id: Slug from :meth:`list_indexes`.
            days: Days of history to return. Defaults to the API's own 180.
        """
        return IndexHistoryResponse.from_dict(
            self._get(f"/api/v1/indexes/{index_id}/history", params={"days": days}).json()
        )

    # ── Trackers ─────────────────────────────────────────────────

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

    # ── Screener ─────────────────────────────────────────────────

    def get_screener_fields(self) -> ScreenerFieldCatalog:
        """Every filterable field, with its unit, operators and description.

        Build a filter UI from this rather than hardcoding the list, and you
        inherit new fields as they ship. Returns a
        :class:`~sentisense.types.ScreenerFieldCatalog` with a ``stock`` list
        and an ``etf`` list; the two universes do not share a field vocabulary.

        The ETF ``STRING`` fields (``ISSUER``, ``ASSET_CLASS``,
        ``TRACKED_INDEX``) come back with their ``values`` populated from the
        live universe, so pickers stay current without a client release.
        """
        return ScreenerFieldCatalog.from_dict(self._get("/api/v1/screener/fields").json())

    def list_screens(self) -> List[FeaturedScreen]:
        """The curated screens shipped in the product, each with a runnable plan.

        Each screen's ``plan`` round-trips straight into :meth:`run_screen`
        (or :meth:`run_etf_screen` when ``plan["universe"] == "ETF"``), so a
        curated screen is both a ready-made query and a worked example of the
        plan shape.

        Two conventions in the names are load-bearing: ``+`` means both
        conditions hold, ``vs`` means the two sides disagree.

        Note the filters inside these plans identify their field with ``field``
        rather than ``fieldName``. Both keys are accepted on the way in, so
        read either when inspecting a plan you did not build yourself.
        """
        return [
            FeaturedScreen.from_dict(s)
            for s in (self._get("/api/v1/screener/screens").json().get("screens") or [])
            if s is not None
        ]

    def run_screen(
        self,
        plan: Dict[str, Any],
        *,
        tickers: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> ScreenerResults:
        """Run a screen against the stock universe.

        A plan is ``{"filters": [...], "sort": {...}}``. Every filter is
        ``{"fieldName": "<FIELD>", "op": "<OP>", "value": <number>}``, ANDed
        together; there is no OR, so run two screens and merge. Operators are
        ``GTE``, ``LTE``, ``GT``, ``LT``, ``EQ``, ``NEQ``, ``IN``, ``NOT_IN``,
        and ``sort`` is ``{"fieldName": "...", "dir": "ASC" | "DESC"}``.

        Three field semantics are worth stating outright, because guessing them
        wrong produces a screen that looks fine and means nothing:

        * ``ANALYST_RATING_MEAN`` is **inverted**: it is the vendor's 1-to-5
          scale where ``1.0`` is strong buy. Bullish is ``LTE 2.5``, not
          ``GTE``. Prefer ``ANALYST_BUY_RATIO_PCT``, which runs the intuitive
          direction.
        * ``MA_CROSS_STATE`` is **ordinal**, not a percentage: ``1`` golden
          cross (50-day above 200-day), ``-1`` death cross, ``0`` neither. Use
          ``EQ``.
        * ``SENTIMENT_DIRECTION`` is the sign of the 7-day SentiSense Score
          (``1`` / ``0`` / ``-1``) with a neutral band of plus-or-minus 5.
          Despite the name it is not sentiment polarity, and ``0`` matches only
          an exact zero, so it returns almost nothing.

        Filter the Score fields (``SENTI_SCORE_7D``, ``SENTI_SCORE_1M``,
        ``SCORE_CHANGE_7D``) on the band edges 5 / 13 / 23, not on
        polarity-scale values like ``0.5``, which behave as "any positive
        score". Nulls never match in either direction, so a screen returning
        fewer rows than expected is usually a coverage question rather than a
        threshold one.

        Args:
            plan: The filter and sort plan. Take one from :meth:`list_screens`
                or build your own.
            tickers: Optional ticker subset, for screening a watchlist.
                Omitted means the whole tracked universe.
            limit: Rows to return. Defaults to 100 server-side, caps at 500.
                It sits next to the plan on the request rather than inside it,
                because a plan is a stored object and paging is a transport
                concern.

        Returns:
            A :class:`~sentisense.types.ScreenerResults` whose ``matched``
            counts the rows the plan matched before ``limit`` was applied.
        """
        body: Dict[str, Any] = {"plan": plan}
        if tickers is not None:
            body["tickers"] = tickers
        if limit is not None:
            body["limit"] = limit
        return ScreenerResults.from_dict(
            self._post("/api/v1/screener/execute", json=body).json()
        )

    def run_etf_screen(
        self,
        plan: Dict[str, Any],
        *,
        tickers: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> EtfScreenerResults:
        """Run a screen against the ETF universe.

        Same request shape as :meth:`run_screen`, against a different field
        vocabulary: take the ETF names from
        ``get_screener_fields().etf``. ``IN`` / ``NOT_IN`` take a ``values``
        list instead of ``value`` and are the operators for the string fields
        (``ISSUER``, ``ASSET_CLASS``, ``TRACKED_INDEX``).

        ``CONSTITUENTS_WEIGHTED_SENTISENSE`` is the holdings-weighted
        SentiSense Score across what the fund owns, and is usually the one you
        want; ``DIRECT_SENTISENSE`` is the Score from chatter about the fund
        ticker itself, which on a broad index fund is mostly macro noise.
        ``WEIGHT_COVERED_PCT`` tells you how much of the fund's weight had
        constituent data behind the weighted number.

        Args:
            plan: The filter and sort plan.
            tickers: Optional ETF ticker subset. Omitted means every tracked fund.
            limit: Rows to return. Defaults to 100 server-side, caps at 500.
        """
        body: Dict[str, Any] = {"plan": plan}
        if tickers is not None:
            body["tickers"] = tickers
        if limit is not None:
            body["limit"] = limit
        return EtfScreenerResults.from_dict(
            self._post("/api/v1/screener/etfs/execute", json=body).json()
        )
