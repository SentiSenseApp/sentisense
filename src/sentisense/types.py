"""Typed response models for the SentiSense API.

All models support both attribute access (``price.ticker``) and dict-style
access (``price["ticker"]``) for backward compatibility.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, Generic, Iterator, List, Optional, TypeVar

T = TypeVar("T")


# ── Base ────────────────────────────────────────────────────


@dataclass
class APIModel:
    """Base class providing dict-style access on dataclass instances."""

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    @classmethod
    def from_dict(cls, data: dict) -> "APIModel":
        """Construct from a JSON dict, ignoring unknown keys."""
        if data is None:
            return None  # type: ignore[return-value]
        known = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


# ── Preview wrapper ─────────────────────────────────────────


class PreviewResult(Generic[T]):
    """Transparent proxy wrapping auto-unwrapped API data with preview metadata.

    Access the underlying data via ``.data``, or directly via attribute or item
    access for object-wrapped results. Check ``.is_preview`` and
    ``.preview_reason`` for tier information. ``.total_count`` is the number of
    items that exist behind the response: on a preview it is the size of the full
    dataset, so you can show "showing N of total_count"; on a paged endpoint it is
    the size of the whole matching set on every tier, so compare it against the
    page you were handed to decide whether to fetch the next ``offset``. It is
    ``None`` only on endpoints that return everything and therefore have no page
    to count past.

    For list-wrapped endpoints (e.g. ``get_politician_members()``), prefer
    ``result.data``, ``list(result)``, or ``for item in result`` over
    attribute access, since a list has no named fields to delegate to.
    """

    def __init__(
        self,
        data: T,
        is_preview: bool,
        preview_reason: Optional[str],
        total_count: Optional[int] = None,
    ):
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "is_preview", is_preview)
        object.__setattr__(self, "preview_reason", preview_reason)
        object.__setattr__(self, "total_count", total_count)

    @property
    def data(self) -> T:
        """The unwrapped API payload. Works for both list and object responses."""
        return object.__getattribute__(self, "_data")

    def __getattr__(self, name: str) -> Any:
        data = object.__getattribute__(self, "_data")
        try:
            return getattr(data, name)
        except AttributeError:
            # Fall back to dict-style access when the wrapped data is a plain dict
            # (e.g. endpoints not yet migrated to a typed dataclass). Keeps the proxy's
            # "transparent" promise honest regardless of response shape.
            if isinstance(data, dict) and name in data:
                return data[name]
            raise

    def __getitem__(self, key: Any) -> Any:
        return self._data[key]  # type: ignore[index]

    def __iter__(self) -> Iterator:
        return iter(self._data)  # type: ignore[arg-type]

    def __len__(self) -> int:
        return len(self._data)  # type: ignore[arg-type]

    def __repr__(self) -> str:
        return f"PreviewResult(is_preview={self.is_preview}, data={self._data!r})"


# ── Stock types ─────────────────────────────────────────────


@dataclass
class ExtendedHoursInfo(APIModel):
    """Pre-market or after-hours session view embedded in price / quote responses.

    Present only when the snapshot sees pre-market (04:00-09:30 ET) or after-hours
    (16:00-20:00 ET) activity. ``change`` and ``changePercent`` are server-computed
    versus the regular-session ``currentPrice``.
    """

    session: str = ""  # "pre" or "post"
    price: float = 0.0
    change: float = 0.0
    changePercent: float = 0.0


@dataclass
class StockPrice(APIModel):
    """Latest stock price data, delayed 15 minutes.

    ``currentPrice`` is always the regular-session price (the most recent
    regular-session value during RTH, most recent regular-session close
    otherwise). ``extendedHours`` is populated only during pre-market or
    after-hours sessions.

    ``priceAsOf`` is when the market data behind ``currentPrice`` is from, in
    Unix milliseconds. Read it for freshness rather than ``timestamp``, which is
    when the response was served and therefore always reads as now. It is
    ``None`` outside regular hours and whenever the upstream data carries no
    time of its own, so treat ``None`` as unknown age, not as fresh.
    """

    ticker: str = ""
    currentPrice: float = 0.0
    change: float = 0.0
    changePercent: float = 0.0
    previousClose: float = 0.0
    volume: int = 0
    timestamp: int = 0
    extendedHours: Optional[ExtendedHoursInfo] = None
    # Appended so that any positional construction of this dataclass keeps
    # binding the same arguments.
    priceAsOf: Optional[int] = None
    # Listing lifecycle. ``None`` for an ordinarily listed stock, which is almost every
    # ticker. ``"DELISTED"`` means the company no longer trades publicly and EVERY price
    # field above is frozen at the last trade before ``delistedDate``: it is not a live
    # price, and ``changePercent`` should not be rendered as a market move.
    # ``"PENDING_DELISTING"`` means a merger or take-private is scheduled but the stock
    # still trades normally, so the figures above ARE current; treat it as informational,
    # not as a data-quality warning.
    listingStatus: Optional[str] = None
    # ISO date (YYYY-MM-DD) trading stopped. ``None`` unless ``listingStatus`` is DELISTED.
    delistedDate: Optional[str] = None
    # Why it delisted: "acquired", "take_private", "bankruptcy", "exchange_rule", "merged".
    delistingReason: Optional[str] = None


@dataclass
class StockQuote(APIModel):
    """Aggregate quote snapshot from GET /api/v1/stocks/{ticker}/quote.

    Combines the latest price (delayed 15 minutes), today OHLC, 52-week range,
    market cap, and key fundamentals into a single payload. All fields except ``ticker`` may be
    ``None`` when the upstream data source is unavailable.

    ``currentPrice`` is always the regular-session price. ``extendedHours`` is
    populated only during pre-market or after-hours sessions; see
    :class:`ExtendedHoursInfo` for the nested shape.

    ``priceAsOf`` is when the market data behind ``currentPrice`` is from, in
    Unix milliseconds. Read it for freshness rather than ``timestamp``, which is
    when the response was served and therefore always reads as now. It is
    ``None`` outside regular hours and whenever the upstream data carries no
    time of its own, so treat ``None`` as unknown age, not as fresh.

    ``reportedCurrency`` names the currency the filer reports in ("USD", "KRW",
    ...) and travels with the filing-derived fields (``epsTTM``, ``peRatio``).
    It is ``None`` when the quote carries no filing-derived data; that means the
    currency is unknown, not implicitly USD. Price fields are always quoted in
    the listing currency of the exchange, which for an ADR is USD even when the
    filer reports in something else, so never mix the two.
    """

    ticker: str = ""
    currentPrice: Optional[float] = None
    change: Optional[float] = None
    changePercent: Optional[float] = None
    volume: Optional[int] = None
    open: Optional[float] = None
    dayHigh: Optional[float] = None
    dayLow: Optional[float] = None
    previousClose: Optional[float] = None
    week52High: Optional[float] = None
    week52Low: Optional[float] = None
    marketCap: Optional[float] = None
    peRatio: Optional[float] = None
    epsTTM: Optional[float] = None
    dividendYield: Optional[float] = None
    movingAverage200Day: Optional[float] = None
    timestamp: Optional[int] = None
    extendedHours: Optional[ExtendedHoursInfo] = None
    # Appended rather than grouped with the filing-derived fields above so that any
    # positional construction of this dataclass keeps binding the same arguments.
    reportedCurrency: Optional[str] = None
    priceAsOf: Optional[int] = None
    # Listing lifecycle. ``None`` for an ordinarily listed stock, which is almost every
    # ticker. ``"DELISTED"`` means the company no longer trades publicly and EVERY price
    # field above is frozen at the last trade before ``delistedDate``: it is not a live
    # quote, and ``changePercent`` should not be rendered as a market move.
    # ``"PENDING_DELISTING"`` means a merger or take-private is scheduled but the stock
    # still trades normally, so the figures above ARE current; treat it as informational,
    # not as a data-quality warning.
    listingStatus: Optional[str] = None
    # ISO date (YYYY-MM-DD) trading stopped. ``None`` unless ``listingStatus`` is DELISTED.
    delistedDate: Optional[str] = None
    # Why it delisted: "acquired", "take_private", "bankruptcy", "exchange_rule", "merged".
    delistingReason: Optional[str] = None


@dataclass
class SimilarStock(APIModel):
    """Peer/similar stock with optional price data."""

    symbol: str = ""
    name: str = ""
    # Deprecated: no longer returned by the API; use `symbol` to identify the peer.
    # Will be removed in a future release.
    kbEntityId: Optional[str] = None
    price: Optional[float] = None
    changePercent: Optional[float] = None


@dataclass
class StockDetail(APIModel):
    """Stock with company name and entity metadata.

    The API names the company in two fields: ``simpleName`` is the short display
    name ("Agilent") and ``companyName`` is the legal name ("Agilent
    Technologies, Inc."). ``name`` is a legacy alias the API never sends; it is
    filled from ``simpleName`` so older code keeps working.
    """

    ticker: str = ""
    name: str = ""
    simpleName: str = ""
    companyName: str = ""
    kbEntityId: Optional[str] = None
    urlSlug: Optional[str] = None
    brandColor: Optional[str] = None
    socialDominance: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.simpleName or self.companyName


@dataclass
class MarketStatus(APIModel):
    """Market open/closed status."""

    status: str = ""  # "open" or "closed"
    timestamp: int = 0


# ── Calendar types ──────────────────────────────────────────


@dataclass
class EarningsEvent(APIModel):
    """A single upcoming-earnings entry."""

    ticker: str = ""
    companyName: str = ""
    earningsDate: str = ""  # ISO calendar day "YYYY-MM-DD"
    earningsTime: str = ""  # before_open | after_close | during_market | unknown
    fiscalQuarter: Optional[str] = None
    confirmed: bool = False
    estimatedEps: Optional[float] = None


@dataclass
class CalendarMeta(APIModel):
    """Provenance for a calendar response."""

    generatedAt: Optional[int] = None  # epoch seconds
    windowStart: Optional[str] = None  # ISO date
    windowEnd: Optional[str] = None  # ISO date
    count: int = 0
    source: str = "sentisense"


@dataclass
class EarningsCalendar(APIModel):
    """Upcoming earnings calendar: events plus window metadata.

    Note: no ``data`` field by design (it would shadow ``PreviewResult.data``).
    """

    earnings: List[EarningsEvent] = field(default_factory=list)
    metadata: Optional[CalendarMeta] = None

    @classmethod
    def from_dict(cls, data: dict) -> "EarningsCalendar":
        return cls(
            earnings=[EarningsEvent.from_dict(e) for e in data.get("earnings", [])],
            metadata=CalendarMeta.from_dict(data.get("metadata") or {}),
        )


# ── Earnings analysis report types ──────────────────────────


@dataclass
class EarningsKpiHighlight(APIModel):
    """One KPI card on a reported quarter.

    ``value`` and ``yoy`` are display strings, already formatted (``"$109.4B"``,
    ``"+16% YoY"``), not numbers to compute with. ``yoy`` is ``None`` when the
    quarter carries no year-over-year comparison for that line.
    """

    label: str = ""
    value: str = ""
    yoy: Optional[str] = None


@dataclass
class EarningsSource(APIModel):
    """A citation backing a reported quarter."""

    title: str = ""
    url: str = ""


@dataclass
class EarningsQuarter(APIModel):
    """One fiscal quarter of the earnings analysis report.

    The wire shape depends on the caller's tier, so branch on the envelope's
    ``is_preview`` rather than on field presence. ``fiscalPeriod``,
    ``reportDate``, ``headline``, ``hasTranscript``, ``generatedAt`` and
    ``source`` arrive on both tiers.

    PRO adds the bodies: ``summaryMd``, the full ``kpiHighlights``,
    ``guidance``, ``transcriptSummaryMd``, ``transcriptHighlights``,
    ``transcriptGeneratedAt`` and ``sources``.

    The FREE preview replaces those bodies with shape: up to two
    ``kpiHighlights`` cards (without ``yoy``) plus ``kpiHighlightCount``,
    the section titles in ``summaryTopics`` and ``transcriptTopics``, and
    ``hasGuidance`` with ``guidanceDirection`` in place of the guidance
    language. It never carries a body, a KPI history, or a guidance figure.

    Absence is explicit: a quarter with no call summary sets
    ``hasTranscript`` to ``False`` rather than dropping the concept, so a
    client can say "no call summary yet" instead of rendering nothing.
    """

    fiscalPeriod: str = ""
    reportDate: str = ""  # ISO calendar day "YYYY-MM-DD"
    headline: str = ""
    hasTranscript: bool = False
    generatedAt: Optional[int] = None  # epoch seconds
    source: Optional[str] = None  # "press_release" | "transcript"

    # PRO
    summaryMd: Optional[str] = None
    kpiHighlights: List[EarningsKpiHighlight] = field(default_factory=list)
    guidance: Optional[str] = None
    transcriptSummaryMd: Optional[str] = None
    transcriptHighlights: List[EarningsKpiHighlight] = field(default_factory=list)
    transcriptGeneratedAt: Optional[int] = None  # epoch seconds
    sources: List[EarningsSource] = field(default_factory=list)

    # FREE preview
    kpiHighlightCount: Optional[int] = None
    summaryTopics: List[str] = field(default_factory=list)
    transcriptTopics: List[str] = field(default_factory=list)
    hasGuidance: Optional[bool] = None
    guidanceDirection: Optional[str] = None  # RAISED | CUT | HELD | MIXED | None

    @classmethod
    def from_dict(cls, data: dict) -> "EarningsQuarter":
        known = {f.name for f in dataclasses.fields(cls)}
        nested = {"kpiHighlights", "transcriptHighlights", "sources"}
        base = {k: v for k, v in data.items() if k in known and k not in nested}
        return cls(
            **base,
            kpiHighlights=[
                EarningsKpiHighlight.from_dict(k) for k in (data.get("kpiHighlights") or [])
            ],
            transcriptHighlights=[
                EarningsKpiHighlight.from_dict(k)
                for k in (data.get("transcriptHighlights") or [])
            ],
            sources=[EarningsSource.from_dict(s) for s in (data.get("sources") or [])],
        )


@dataclass
class RecentEarningsEntry(APIModel):
    """One company that reported inside the recent window."""

    ticker: str = ""
    fiscalPeriod: str = ""
    reportDate: str = ""  # ISO calendar day "YYYY-MM-DD"
    headline: str = ""
    hasTranscriptSummary: bool = False
    generatedAt: Optional[int] = None  # epoch seconds


# ── Insider types ───────────────────────────────────────────


@dataclass
class InsiderActivitySummary(APIModel):
    """Aggregated insider activity for a single ticker."""

    ticker: str = ""
    companyName: str = ""
    tradeCount: int = 0
    insiderCount: int = 0
    totalShares: int = 0
    totalValue: int = 0
    latestDate: str = ""
    latestInsider: str = ""
    latestTitle: str = ""


@dataclass
class InsiderActivity(APIModel):
    """Market-wide insider activity split into buys and sells."""

    buys: List[InsiderActivitySummary] = field(default_factory=list)
    sells: List[InsiderActivitySummary] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "InsiderActivity":
        return cls(
            buys=[InsiderActivitySummary.from_dict(b) for b in data.get("buys", [])],
            sells=[InsiderActivitySummary.from_dict(s) for s in data.get("sells", [])],
        )


@dataclass
class InsiderTrade(APIModel):
    """Individual insider transaction from SEC Form 4."""

    ticker: str = ""
    companyName: str = ""
    insiderName: str = ""
    insiderTitle: str = ""
    insiderRelation: str = ""
    officer: bool = False
    director: bool = False
    tenPctOwner: bool = False
    transactionDate: str = ""
    filedDate: str = ""
    # Raw SEC Form 4 code. Only "P" and "S" are open-market trades; "F" is shares withheld
    # by the issuer to cover taxes at vest, which is a corporate mechanic rather than a
    # decision to sell. Tally discretionary buying and selling from this field.
    transactionCode: str = ""
    # "BUY" | "SELL" | "EXERCISE" | "AWARD" | "GIFT" | "OTHER". A simplification of
    # transactionCode, so code "F" arrives here as "SELL": filtering to BUY/SELL alone
    # overstates selling. Insider uses BUY/SELL, NOT the congress PURCHASE/SALE vocab.
    transactionType: str = ""
    securityTitle: str = ""
    sharesTransacted: int = 0
    pricePerShare: Optional[float] = None
    totalValue: Optional[int] = None
    sharesOwnedAfter: Optional[int] = None
    directOwnership: bool = True
    rule10b51: bool = False


@dataclass
class ClusterBuy(APIModel):
    """Cluster buy signal: 3+ insiders buying the same stock."""

    ticker: str = ""
    companyName: str = ""
    insiderCount: int = 0
    tradeCount: int = 0
    totalShares: int = 0
    totalValue: int = 0
    firstBuyDate: str = ""
    lastBuyDate: str = ""


# ── Politician types ────────────────────────────────────────


@dataclass
class AssetMetadata(APIModel):
    """Asset-type-specific detail on a congressional trade.

    ``None`` for plain ``Stock``/``ETF`` holdings. When present it is a
    discriminated ("oneOf") shape keyed by ``kind``. Today only options carry
    metadata: ``kind="OPTION"`` -> ``optionType`` (``"CALL"``/``"PUT"``),
    ``strikePrice`` (dollars), ``expirationDate`` (ISO ``"YYYY-MM-DD"``). Only
    the fields relevant to ``kind`` are present.
    """

    kind: Optional[str] = None  # discriminator; currently only "OPTION"
    # OPTION variant
    optionType: Optional[str] = None  # "CALL" or "PUT"
    strikePrice: Optional[float] = None  # strike in dollars
    expirationDate: Optional[str] = None  # ISO "YYYY-MM-DD"


@dataclass
class CongressTrade(APIModel):
    """Congressional STOCK Act trade disclosure."""

    politicianName: str = ""
    firstName: str = ""
    lastName: str = ""
    chamber: str = ""  # "SENATE" or "HOUSE"
    party: str = ""
    state: str = ""
    bioguideId: str = ""
    ticker: str = ""
    assetDescription: str = ""
    # "PURCHASE" | "SALE" | "EXCHANGE" | "OTHER". Congress uses PURCHASE/SALE, NOT the insider
    # endpoint's BUY/SELL vocab (a filter written for one returns zero on the other).
    transactionType: str = ""
    transactionDate: str = ""
    disclosureDate: str = ""
    amountRange: str = ""
    amountMin: int = 0
    amountMax: int = 0
    owner: str = ""
    urlSlug: str = ""
    imageUrl: Optional[str] = None
    assetType: Optional[str] = None  # "Stock", "ETF", or "Stock Option"
    # Structured asset detail (None for plain Stock/ETF). For options carries
    # optionType/strikePrice/expirationDate under kind="OPTION".
    assetMetadata: Optional[AssetMetadata] = None
    disclosureDelayDays: Optional[int] = None
    sentiSenseScore: Optional[float] = None

    @classmethod
    def from_dict(cls, data: dict) -> "CongressTrade":
        if data is None:
            return None  # type: ignore[return-value]
        known = {f.name for f in dataclasses.fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known}
        if data.get("assetMetadata"):
            kwargs["assetMetadata"] = AssetMetadata.from_dict(data["assetMetadata"])
        return cls(**kwargs)


@dataclass
class PoliticianSummary(APIModel):
    """Politician profile with trading summary statistics."""

    urlSlug: str = ""
    displayName: str = ""
    firstName: str = ""
    lastName: str = ""
    chamber: str = ""
    party: str = ""
    state: str = ""
    bioguideId: str = ""
    totalTrades: int = 0
    purchaseCount: int = 0
    saleCount: int = 0
    imageUrl: Optional[str] = None
    kbEntityId: Optional[str] = None
    latestTradeDate: Optional[str] = None
    sentiSenseScore: Optional[float] = None
    #: True for a member who has left Congress. The members roster serves only sitting
    #: members, so this reads True only on a member detail or directory response. Render
    #: the tense accordingly ("Former Senator").
    former: bool = False
    #: Year the member left Congress, e.g. ``"2021"``. None for a sitting member.
    servedUntil: Optional[str] = None


@dataclass
class PoliticianDetail(APIModel):
    """Full politician profile with recent trades and top tickers."""

    profile: Optional[PoliticianSummary] = None
    recentTrades: List[CongressTrade] = field(default_factory=list)
    topTickers: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "PoliticianDetail":
        return cls(
            profile=PoliticianSummary.from_dict(data["profile"]) if data.get("profile") else None,
            recentTrades=[CongressTrade.from_dict(t) for t in data.get("recentTrades", [])],
            topTickers=data.get("topTickers", []),
        )


# ── Insight types ───────────────────────────────────────────


@dataclass
class InsightDocRef(APIModel):
    """Source document referenced by an insight."""

    url: str = ""
    type: str = ""  # "News", "X", "Reddit", "YouTube", etc.


@dataclass
class Insight(APIModel):
    """AI-generated trading signal."""

    insightType: str = ""
    insightText: str = ""
    confidence: float = 0.0
    urgency: str = ""  # "low", "medium", "high"
    generatedAt: int = 0
    insightId: Optional[str] = None
    category: Optional[str] = None  # "SENTIMENT", "TRENDING", "TECHNICAL", "FUNDAMENTAL", "PERSONALIZED"
    docRefs: Optional[List[InsightDocRef]] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Insight":
        doc_refs = None
        if data.get("docRefs"):
            doc_refs = [InsightDocRef.from_dict(r) for r in data["docRefs"]]
        known = {f.name for f in dataclasses.fields(cls)}
        base = {k: v for k, v in data.items() if k in known and k != "docRefs"}
        return cls(**base, docRefs=doc_refs)


# ── Document types ──────────────────────────────────────────


@dataclass
class SentimentEntry(APIModel):
    """Per-entity sentiment classification within a document."""

    entityId: str = ""
    entityType: str = ""
    sentiment: str = ""
    ticker: Optional[str] = None
    name: Optional[str] = None


@dataclass
class Document(APIModel):
    """News or social media document with sentiment metrics."""

    id: str = ""
    url: str = ""
    source: str = ""
    published: int = 0
    averageSentiment: float = 0.0
    reliability: float = 0.0
    sourceName: Optional[str] = None
    sentiment: Optional[List[SentimentEntry]] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Document":
        sentiments = None
        if data.get("sentiment"):
            sentiments = [SentimentEntry.from_dict(s) for s in data["sentiment"]]
        known = {f.name for f in dataclasses.fields(cls)}
        base = {k: v for k, v in data.items() if k in known and k != "sentiment"}
        return cls(**base, sentiment=sentiments)


@dataclass
class DocumentSearchResponse(APIModel):
    """Wrapped document search response with metadata."""

    documents: List[Document] = field(default_factory=list)
    totalCount: int = 0
    searchTicker: Optional[str] = None
    source: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "DocumentSearchResponse":
        return cls(
            documents=[Document.from_dict(d) for d in data.get("documents", [])],
            totalCount=data.get("totalCount", 0),
            searchTicker=data.get("searchTicker"),
            source=data.get("source"),
            startDate=data.get("startDate"),
            endDate=data.get("endDate"),
        )


@dataclass
class StoryCluster(APIModel):
    """News story cluster metadata."""

    id: str = ""
    title: str = ""
    clusterSize: int = 0
    averageSentiment: float = 0.0
    clusteredAt: int = 0  # epoch seconds when our pipeline assembled the cluster


@dataclass
class Story(APIModel):
    """AI-curated news story with impact score and tickers."""

    cluster: Optional[StoryCluster] = None
    #: Human-formatted labels for display, e.g. ``"Apple Inc (AAPL)"``. For display
    #: only; do not parse symbols out of these. Use ``tickers`` programmatically.
    displayTickers: List[str] = field(default_factory=list)
    #: Bare ticker symbols for programmatic use, e.g. ``"AAPL"``. Use these to filter
    #: or look up stocks.
    tickers: List[str] = field(default_factory=list)
    impactScore: float = 0.0
    brokeAt: Optional[int] = None
    primaryEntityNames: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Story":
        cluster = StoryCluster.from_dict(data["cluster"]) if data.get("cluster") else None
        known = {f.name for f in dataclasses.fields(cls)}
        base = {k: v for k, v in data.items() if k in known and k != "cluster"}
        return cls(**base, cluster=cluster)


# ── Market types ────────────────────────────────────────────


@dataclass
class MarketSummary(APIModel):
    """AI-generated market summary."""

    #: Not populated by the API (always 0); retained so existing consumers keep working.
    totalMentions: int = 0
    #: Not populated by the API (always empty); retained so existing consumers keep working.
    topActiveStocks: List[str] = field(default_factory=list)
    lastUpdated: int = 0
    headline: Optional[str] = None
    expandedContent: Optional[str] = None
    generatedAt: Optional[int] = None


# ── Institutional types ─────────────────────────────────────


@dataclass
class Quarter(APIModel):
    """Available 13F reporting quarter."""

    value: str = ""
    label: str = ""
    reportDate: str = ""


@dataclass
class InstitutionalFlow(APIModel):
    """Institutional flow data for a single ticker."""

    ticker: str = ""
    companyName: str = ""
    totalSharesBought: int = 0
    totalSharesSold: int = 0
    netSharesChange: int = 0
    newPositions: int = 0
    increasedPositions: int = 0
    decreasedPositions: int = 0
    soldOutPositions: int = 0
    indexFundNetChange: int = 0
    hedgeFundNetChange: int = 0
    # Net share change contributed by each remaining filer category this quarter.
    activistNetChange: int = 0
    pensionNetChange: int = 0
    bankNetChange: int = 0
    insuranceNetChange: int = 0
    mutualFundNetChange: int = 0
    sovereignWealthNetChange: int = 0
    endowmentNetChange: int = 0
    conglomerateNetChange: int = 0
    activistActivity: bool = False
    reportDate: str = ""
    # Quarterly average closing price used to weight the dollar flow. None when no
    # price is cached for this (quarter, ticker) yet.
    avgClosePrice: Optional[float] = None
    # Dollar-weighted net flow: netSharesChange × avgClosePrice. 0 when avgClosePrice
    # is missing, so clients should fall back to displaying netSharesChange.
    dollarFlowUsd: float = 0.0


@dataclass
class InstitutionalFlows(APIModel):
    """Market flows split into inflows and outflows.

    When ``report_date`` is omitted from the request, the server returns the latest
    available quarter and populates ``reportDate`` here so callers know which quarter
    they received. ``isPending`` is True for a still-open 13F filing window (within 45
    days of quarter end), where only early filers are represented; ``filerCount`` and
    ``baselineFilerCount`` then give the coverage (e.g. 578 of 8789 filers). All three
    coverage fields are None on a fully-filed quarter and on legacy responses.
    """

    inflows: List[InstitutionalFlow] = field(default_factory=list)
    outflows: List[InstitutionalFlow] = field(default_factory=list)
    reportDate: Optional[str] = None
    isPending: Optional[bool] = None
    filerCount: Optional[int] = None
    baselineFilerCount: Optional[int] = None

    @classmethod
    def from_dict(cls, data: dict) -> "InstitutionalFlows":
        return cls(
            inflows=[InstitutionalFlow.from_dict(f) for f in data.get("inflows", [])],
            outflows=[InstitutionalFlow.from_dict(f) for f in data.get("outflows", [])],
            reportDate=data.get("reportDate"),
            isPending=data.get("isPending"),
            filerCount=data.get("filerCount"),
            baselineFilerCount=data.get("baselineFilerCount"),
        )


# ── Options types ───────────────────────────────────────────
#
# Every reading in this family is end of day, and every percentile is measured against
# that ticker's OWN trailing history rather than against other tickers. Fields the server
# cannot compute are omitted from the JSON entirely, so each one defaults to ``None``:
# an omitted percentile means "not enough history yet", never zero.


@dataclass
class OptionsAggregate(APIModel):
    """One session's options aggregate for a ticker.

    Shared by the dossier's ``latest`` and by every element of an
    :class:`OptionsHistory` series, so a chart built off one reads the other.
    """

    date: Optional[str] = None
    callVol: Optional[int] = None
    putVol: Optional[int] = None
    callOi: Optional[int] = None
    putOi: Optional[int] = None
    pcVol: Optional[float] = None
    """Put/call volume ratio. Omitted when call volume is zero."""
    pcOi: Optional[float] = None
    """Put/call open-interest ratio."""
    vwIv: Optional[float] = None
    """Volume-weighted implied volatility."""
    atmIv: Optional[float] = None
    """At-the-money implied volatility as a fraction, so ``0.42`` is 42%."""
    skew25d: Optional[float] = None
    """``iv25p - iv25c``: positive means puts are bid up relative to calls."""
    atmIv60: Optional[float] = None
    """Roughly 60-day at-the-money implied volatility: the term structure."""
    atmIv90: Optional[float] = None
    """Roughly 90-day at-the-money implied volatility."""
    iv25c: Optional[float] = None
    """Raw 25-delta call implied volatility."""
    iv25p: Optional[float] = None
    """Raw 25-delta put implied volatility."""
    netDelta: Optional[float] = None
    notionalVol: Optional[float] = None
    """Premium traded this session: volume times mark times 100."""
    contracts: Optional[int] = None


@dataclass
class OptionsContext(APIModel):
    """Percentiles of an :class:`OptionsAggregate`, against the ticker's own history.

    A percentile whose trailing window holds too few observations is omitted while the
    baseline builds, which is why a covered ticker can answer with readings and no
    percentiles at all.
    """

    pcVolPctl1y: Optional[float] = None
    pcVolPctl5y: Optional[float] = None
    pcOiPctl1y: Optional[float] = None
    ivRank1y: Optional[float] = None
    """Where today's at-the-money implied volatility sits in its own trailing year, 0-100."""
    skewPctl1y: Optional[float] = None
    observations1y: Optional[int] = None


@dataclass
class OptionsWall(APIModel):
    """One open-interest concentration at a strike."""

    strike: Optional[float] = None
    oi: Optional[int] = None


@dataclass
class OptionsOiWalls(APIModel):
    """Open-interest wall structure for the dossier's expiry, up to three walls a side."""

    expiry: Optional[str] = None
    maxPain: Optional[float] = None
    callWalls: List[OptionsWall] = field(default_factory=list)
    putWalls: List[OptionsWall] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "OptionsOiWalls":
        if data is None:
            return None  # type: ignore[return-value]
        return cls(
            expiry=data.get("expiry"),
            maxPain=data.get("maxPain"),
            callWalls=[OptionsWall.from_dict(w) for w in (data.get("callWalls") or [])],
            putWalls=[OptionsWall.from_dict(w) for w in (data.get("putWalls") or [])],
        )


@dataclass
class OptionsUnusualContract(APIModel):
    """A contract whose session volume far exceeds its open interest: fresh positioning."""

    contract: Optional[str] = None
    """Exchange-style option symbol, e.g. ``"NVDA260821C00200000"``."""
    type: Optional[str] = None
    """Side of the contract. Arrives lower case, so compare case-insensitively."""
    strike: Optional[float] = None
    expiry: Optional[str] = None
    dte: Optional[int] = None
    """Days to expiry."""
    volume: Optional[int] = None
    oi: Optional[int] = None
    volOiRatio: Optional[float] = None
    premium: Optional[float] = None


@dataclass
class OptionsSummary(APIModel):
    """The end-of-day options dossier for one stock or ETF.

    ``asOf`` is the latest completed session and the data refreshes the following
    morning, so this is positioning rather than a quote feed.
    """

    asOf: Optional[str] = None
    sentiment: Optional[float] = None
    """Positioning lean for the session, roughly -1 to 1, negative for put-heavy."""
    latest: Optional[OptionsAggregate] = None
    context: Optional[OptionsContext] = None
    oiWalls: Optional[OptionsOiWalls] = None
    unusual: List[OptionsUnusualContract] = field(default_factory=list)
    """Top contracts by premium."""

    @classmethod
    def from_dict(cls, data: dict) -> "OptionsSummary":
        if data is None:
            return None  # type: ignore[return-value]
        # `is not None`, never truthiness: a ticker whose baseline is still building sends
        # `context: {}`, an empty-but-present object. Treated as falsy that becomes a None
        # context, which reads as "the server said nothing about percentiles" when it in
        # fact said "there are none yet". Same for the other nested objects.
        return cls(
            asOf=data.get("asOf"),
            sentiment=data.get("sentiment"),
            latest=(
                OptionsAggregate.from_dict(data["latest"])
                if data.get("latest") is not None
                else None
            ),
            context=(
                OptionsContext.from_dict(data["context"])
                if data.get("context") is not None
                else None
            ),
            oiWalls=(
                OptionsOiWalls.from_dict(data["oiWalls"])
                if data.get("oiWalls") is not None
                else None
            ),
            unusual=[OptionsUnusualContract.from_dict(u) for u in (data.get("unusual") or [])],
        )


@dataclass
class OptionsHistory(APIModel):
    """The daily options aggregates for one ticker as a time series, oldest first.

    Unlike the dossier, this never reports no coverage with a null payload: an uncovered
    ticker, an unknown symbol and a covered ticker with nothing stored yet all answer with
    this object and an empty ``series``, so check the list rather than the payload.

    ``window`` echoes what the server actually served, which need not be what was asked
    for: an unrecognised value clamps to ``"1y"``, and a free key is held at ``"1y"``
    whatever it requests.
    """

    ticker: Optional[str] = None
    window: Optional[str] = None
    series: List[OptionsAggregate] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "OptionsHistory":
        if data is None:
            return None  # type: ignore[return-value]
        return cls(
            ticker=data.get("ticker"),
            window=data.get("window"),
            series=[OptionsAggregate.from_dict(s) for s in (data.get("series") or [])],
        )


@dataclass
class OptionsOverviewRow(APIModel):
    """One ticker's row on the market-wide options radar.

    A row whose baseline is still building carries its raw readings with the percentiles
    and ``interestScore`` omitted, so missing scores mean "not enough history yet".
    """

    ticker: Optional[str] = None
    name: Optional[str] = None
    """Company name, or the fund name on an ETF row. Omitted when unmapped."""
    sector: Optional[str] = None
    """Sector on a stock row. On an ETF row this carries the fund's asset class
    (``"Equity"``, ``"Bond"``, ``"Commodity"``, ...) rather than a sector, so the two
    boards' values must not feed one sector breakdown."""
    asOf: Optional[str] = None
    sentiment: Optional[float] = None
    """Options-implied positioning lean, roughly -1 to 1, negative for put-heavy."""
    interestScore: Optional[float] = None
    """Composite 0-100 blend of how extreme this row's readings are."""
    pcVol: Optional[float] = None
    pcVolPctl1y: Optional[float] = None
    atmIv: Optional[float] = None
    ivRank1y: Optional[float] = None
    skew25d: Optional[float] = None
    skewPctl1y: Optional[float] = None
    notionalVol: Optional[float] = None
    ivMove20: Optional[float] = None
    """Signed change of ``atmIv`` against its ~20-session mean. Rank by absolute value."""
    observations1y: Optional[int] = None
    unusualCount: Optional[int] = None
    maxVolOiRatio: Optional[float] = None
    maxUnusualPremium: Optional[float] = None
    wallSide: Optional[str] = None
    """Side of the single heaviest open-interest wall, ``"call"`` or ``"put"``."""
    wallStrike: Optional[float] = None
    wallShare: Optional[float] = None
    """That wall's share of its own side's open interest, 0 to 1."""


@dataclass
class OptionsOverview(APIModel):
    """The market-wide options radar: two separately-ranked boards plus their aggregates.

    ``rows`` is the covered stock universe and ``etfRows`` is the covered ETF universe,
    each already sorted by ``interestScore`` descending with unscored building-baseline
    rows last. Do not concatenate them. Every reading behind a row's score is a percentile
    of that ticker's own past, so an ETF's 90th percentile and a stock's 90th percentile
    are measured against different histories and a combined ranking means nothing.

    The aggregates split the same way: ``medianIvRank``, ``marketPcVol``, ``extremeCount``
    and ``coverageCount`` describe the stock board alone, and the ``etf``-prefixed fields
    describe the ETF board. On a free key ``etfTotalCount`` reports the full ETF board the
    way the envelope's ``total_count`` reports the full stock board.
    """

    asOf: Optional[str] = None
    medianIvRank: Optional[float] = None
    marketPcVol: Optional[float] = None
    extremeCount: Optional[int] = None
    coverageCount: Optional[int] = None
    rows: List[OptionsOverviewRow] = field(default_factory=list)
    etfRows: List[OptionsOverviewRow] = field(default_factory=list)
    etfMedianIvRank: Optional[float] = None
    etfMarketPcVol: Optional[float] = None
    etfExtremeCount: Optional[int] = None
    etfCoverageCount: Optional[int] = None
    etfTotalCount: Optional[int] = None

    @classmethod
    def from_dict(cls, data: dict) -> "OptionsOverview":
        if data is None:
            return None  # type: ignore[return-value]
        known = {f.name for f in dataclasses.fields(cls)}
        kwargs = {
            k: v for k, v in data.items() if k in known and k not in ("rows", "etfRows")
        }
        kwargs["rows"] = [OptionsOverviewRow.from_dict(r) for r in (data.get("rows") or [])]
        kwargs["etfRows"] = [
            OptionsOverviewRow.from_dict(r) for r in (data.get("etfRows") or [])
        ]
        return cls(**kwargs)


# ── KPI types ───────────────────────────────────────────────


@dataclass
class KpiDataPoint(APIModel):
    """One period value in a KPI time series."""

    period: str = ""           # e.g. "Q2 FY2026"
    date: str = ""             # ISO date, e.g. "2025-12-27"
    value: float = 0.0
    isEstimate: Optional[bool] = None  # preliminary flag, often null


@dataclass
class KpiSeries(APIModel):
    """A single KPI time series for a company."""

    id: str = ""               # e.g. "iphone_revenue"
    name: str = ""             # e.g. "iPhone Revenue"
    category: str = ""         # e.g. "product_revenue", "segment_revenue"
    unit: str = ""             # e.g. "USD"
    displayFormat: str = ""    # e.g. "currency_abbreviated"
    chartType: str = ""        # e.g. "bar", "line"
    values: List[KpiDataPoint] = field(default_factory=list)
    sourceRef: Optional[str] = None
    discontinued: Optional[bool] = None
    discontinuedNote: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "KpiSeries":
        values = [KpiDataPoint.from_dict(v) for v in data.get("values", [])]
        known = {f.name for f in dataclasses.fields(cls)}
        base = {k: v for k, v in data.items() if k in known and k != "values"}
        return cls(**base, values=values)


@dataclass
class CompanyKpis(APIModel):
    """Full KPI payload for a company. Returned by ``client.get_company_kpis``."""

    ticker: str = ""
    companyName: str = ""
    cik: Optional[str] = None
    lastUpdated: str = ""
    kpis: List[KpiSeries] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "CompanyKpis":
        kpis = [KpiSeries.from_dict(k) for k in data.get("kpis", [])]
        known = {f.name for f in dataclasses.fields(cls)}
        base = {k: v for k, v in data.items() if k in known and k != "kpis"}
        return cls(**base, kpis=kpis)


@dataclass
class KpiCoverageEntry(APIModel):
    """One ticker with curated KPI coverage. Returned by ``client.list_kpi_coverage``."""

    ticker: str = ""
    companyName: str = ""
    lastUpdated: str = ""
    kpiCount: int = 0


@dataclass
class KpiCoverage(APIModel):
    """Coverage listing envelope: count + list of covered tickers."""

    count: int = 0
    tickers: List[KpiCoverageEntry] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "KpiCoverage":
        return cls(
            count=data.get("count", 0),
            tickers=[KpiCoverageEntry.from_dict(t) for t in data.get("tickers", [])],
        )


@dataclass
class KpiTypeEntry(APIModel):
    """Lightweight KPI metadata tuple. Returned by ``client.get_kpi_types``."""

    id: str = ""
    name: str = ""
    category: str = ""
    chartType: str = ""


# ── Fundamentals types ───────────────────────────────────────


@dataclass
class FundamentalsPeriod(APIModel):
    """One reporting period from the fundamentals catalog.

    Returned by ``client.get_fundamentals_periods``. Carries the authoritative
    fiscal labeling as filed with the SEC, useful for mapping a period-end
    ``date`` to its fiscal quarter/year (or driving a period picker).

    Mirrors the Node SDK's ``FundamentalsPeriod``, and additionally exposes
    ``periodEndDate``/``filingDate``/``timeframe`` from the wire response.
    """

    fiscalPeriod: str = ""           # "Q1".."Q4", "FY", or "TTM"
    fiscalYear: str = ""             # e.g. "2026" (string on the wire)
    periodEndDate: str = ""          # ISO date, e.g. "2025-10-26"
    filingDate: Optional[str] = None  # ISO date the report was filed
    timeframe: Optional[str] = None  # "quarterly" or "annual"


# ── ETF types ────────────────────────────────────────────────


@dataclass
class EtfInfo(APIModel):
    """One row from ``client.list_etfs()``."""

    ticker: str = ""
    name: str = ""
    kbEntityId: Optional[str] = None
    urlSlug: Optional[str] = None
    issuer: Optional[str] = None
    trackedIndex: Optional[str] = None
    assetClass: Optional[str] = None
    # Curated landscape card image for the fund, suitable for a list row or a
    # profile header. Distinct from a square logo mark. None when the fund has
    # no curated image assigned.
    imageUrl: Optional[str] = None


@dataclass
class EtfHolding(APIModel):
    """One per-stock holding inside an ETF composition."""

    ticker: str = ""
    name: Optional[str] = None
    weightPct: float = 0.0  # holding weight in the fund as a percentage (0-100)
    firstSeen: Optional[str] = None  # ISO date 'YYYY-MM-DD' when this holding first appeared


@dataclass
class EtfHoldings(APIModel):
    """Full composition for an ETF. Returned by ``client.get_etf_holdings``."""

    ticker: str = ""
    issuer: str = ""
    issuerEndpoint: Optional[str] = None
    asOfDate: str = ""  # ISO date 'YYYY-MM-DD' from the issuer
    fetchedAt: Optional[int] = None  # epoch seconds when SentiSense refreshed the composition
    nextRefreshDue: str = ""  # ISO date 'YYYY-MM-DD' when the next refresh is scheduled
    totalHoldings: int = 0
    holdings: List[EtfHolding] = field(default_factory=list)
    partial: Optional[bool] = None
    totalKnownHoldings: Optional[int] = None

    @classmethod
    def from_dict(cls, data: dict) -> "EtfHoldings":
        if data is None:
            return None  # type: ignore[return-value]
        return cls(
            ticker=data.get("ticker", ""),
            issuer=data.get("issuer", ""),
            issuerEndpoint=data.get("issuerEndpoint"),
            asOfDate=data.get("asOfDate", ""),
            fetchedAt=data.get("fetchedAt"),
            nextRefreshDue=data.get("nextRefreshDue", ""),
            totalHoldings=data.get("totalHoldings", 0),
            holdings=[EtfHolding.from_dict(h) for h in data.get("holdings", [])],
            partial=data.get("partial"),
            totalKnownHoldings=data.get("totalKnownHoldings"),
        )


@dataclass
class EtfAggregateCoverage(APIModel):
    """Coverage block embedded in every ETF aggregate response. Tells the consumer how
    much of fund AUM the underlying per-stock data covered."""

    holdingsCount: int = 0
    holdingsCovered: int = 0
    # Sum of weights (0-100) for the covered holdings, i.e. already in percent
    # units. A fund where 95% of AUM has per-stock coverage reports 95.0, not 0.95.
    weightCovered: float = 0.0
    partial: Optional[bool] = None
    totalKnownHoldings: Optional[int] = None


@dataclass
class WeightedConsensus(APIModel):
    """Holdings-weighted analyst consensus headline."""

    upsidePercent: float = 0.0
    consensusLabel: str = ""
    distribution: Dict[str, float] = field(default_factory=dict)
    totalAnalysts: int = 0


@dataclass
class EtfAnalystContributor(APIModel):
    """One per-holding contribution to the weighted analyst consensus."""

    ticker: str = ""
    weightPct: float = 0.0
    upsidePercent: float = 0.0
    consensusLabel: str = ""
    contributionPp: float = 0.0


@dataclass
class EtfAnalystAggregate(APIModel):
    """Top-level shape returned by ``client.get_etf_analyst_aggregate``."""

    ticker: str = ""
    asOfDate: str = ""  # ISO date 'YYYY-MM-DD'
    computedAt: Optional[int] = None  # epoch seconds
    coverage: Optional[EtfAggregateCoverage] = None
    weightedConsensus: Optional[WeightedConsensus] = None
    topContributors: List[EtfAnalystContributor] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "EtfAnalystAggregate":
        if data is None:
            return None  # type: ignore[return-value]
        tc = data.get("topContributors") or []
        return cls(
            ticker=data.get("ticker", ""),
            asOfDate=data.get("asOfDate", ""),
            computedAt=data.get("computedAt"),
            coverage=EtfAggregateCoverage.from_dict(data.get("coverage")) if data.get("coverage") else None,
            weightedConsensus=WeightedConsensus.from_dict(data.get("weightedConsensus")) if data.get("weightedConsensus") else None,
            topContributors=[EtfAnalystContributor.from_dict(c) for c in tc],
        )


@dataclass
class WeightedNetFlow(APIModel):
    """Holdings-weighted SEC Form 4 net flow headline. ``netDollars`` is signed
    (negative = net selling across the fund's constituents)."""

    netDollars: int = 0
    buyDollars: int = 0
    sellDollars: int = 0
    buyTradeCount: int = 0
    sellTradeCount: int = 0
    distinctInsiderCount: int = 0


@dataclass
class EtfInsiderContributor(APIModel):
    """One per-holding contribution to the weighted insider net flow."""

    ticker: str = ""
    weightPct: float = 0.0
    netDollars: int = 0
    weightedNetDollars: int = 0
    tradeCount: int = 0


@dataclass
class EtfInsiderAggregate(APIModel):
    """Top-level shape returned by ``client.get_etf_insider_aggregate``."""

    ticker: str = ""
    asOfDate: str = ""  # ISO date 'YYYY-MM-DD'
    computedAt: Optional[int] = None  # epoch seconds
    lookbackDays: int = 30
    coverage: Optional[EtfAggregateCoverage] = None
    weightedNetFlow: Optional[WeightedNetFlow] = None
    topContributors: List[EtfInsiderContributor] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "EtfInsiderAggregate":
        if data is None:
            return None  # type: ignore[return-value]
        tc = data.get("topContributors") or []
        return cls(
            ticker=data.get("ticker", ""),
            asOfDate=data.get("asOfDate", ""),
            computedAt=data.get("computedAt"),
            lookbackDays=data.get("lookbackDays", 30),
            coverage=EtfAggregateCoverage.from_dict(data.get("coverage")) if data.get("coverage") else None,
            weightedNetFlow=WeightedNetFlow.from_dict(data.get("weightedNetFlow")) if data.get("weightedNetFlow") else None,
            topContributors=[EtfInsiderContributor.from_dict(c) for c in tc],
        )


@dataclass
class EtfSentimentReading(APIModel):
    """One SentiSense Score reading. Used twice in the sentiment aggregate response
    (constituent-weighted and direct)."""

    sentiSenseScore: float = 0.0
    scoreLabel: str = ""
    asOfTimestamp: Optional[int] = None  # epoch seconds when the underlying metric was produced


@dataclass
class EtfSentimentAggregate(APIModel):
    """Top-level shape returned by ``client.get_etf_sentiment_aggregate``. **Beta**
    as of 2026-05-15: limited fund coverage, so expect 404 for funds outside the
    current coverage window."""

    ticker: str = ""
    asOfDate: str = ""  # ISO date 'YYYY-MM-DD'
    computedAt: Optional[int] = None  # epoch seconds
    coverage: Optional[EtfAggregateCoverage] = None
    constituentsWeighted: Optional[EtfSentimentReading] = None
    direct: Optional[EtfSentimentReading] = None

    @classmethod
    def from_dict(cls, data: dict) -> "EtfSentimentAggregate":
        if data is None:
            return None  # type: ignore[return-value]
        return cls(
            ticker=data.get("ticker", ""),
            asOfDate=data.get("asOfDate", ""),
            computedAt=data.get("computedAt"),
            coverage=EtfAggregateCoverage.from_dict(data.get("coverage")) if data.get("coverage") else None,
            constituentsWeighted=EtfSentimentReading.from_dict(data.get("constituentsWeighted")) if data.get("constituentsWeighted") else None,
            direct=EtfSentimentReading.from_dict(data.get("direct")) if data.get("direct") else None,
        )


# ── Trackers ────────────────────────────────────────────────
#
# Trackers are observational data products. Every tracker (institution rankings,
# hedge-fund reported returns, social trackers, surveillance
# dashboards) returns the same standardized `TrackerSnapshot` envelope.
# Dispatch on ``viewType`` to pick a renderer; consumers write one renderer per
# viewType and get every tracker for free.


@dataclass
class TrackerListing(APIModel):
    """Per-tracker discovery row returned by ``client.list_trackers()``."""

    trackerId: str = ""
    displayName: str = ""
    category: str = ""
    description: str = ""
    viewType: str = ""
    accessTier: str = ""  # "free" or "pro"; pro trackers truncate to a free preview for FREE callers
    methodologyAnchor: str = ""
    refreshIntervalSeconds: int = 0
    canonicalUrl: str = ""


@dataclass
class TrackerListResponse(APIModel):
    """Discovery envelope returned by ``client.list_trackers()``."""

    trackers: List[TrackerListing] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "TrackerListResponse":
        if data is None:
            return None  # type: ignore[return-value]
        return cls(trackers=[TrackerListing.from_dict(t) for t in data.get("trackers", [])])


@dataclass
class TrackerMetricValue(APIModel):
    """A labeled quantitative reading attached to a row, geo region, or
    time-series point. ``value`` is ``Any`` because it can be a number or a
    status string ("Severe", "Resolved") without forcing a separate type."""

    label: str = ""
    value: Any = None
    unit: Optional[str] = None
    trend: Optional[str] = None
    #: Primary-source URL for this cell's value, when the tracker is citation-backed
    #: (e.g. hedge-fund reported returns). ``None`` for computed/uncited cells.
    sourceUrl: Optional[str] = None
    #: Short quote from the primary source supporting this cell's value.
    sourceQuote: Optional[str] = None
    #: The period this cell refers to (e.g. "2025", "2026-YTD"). Present when a
    #: cell's period varies per row, so the column header can stay year-agnostic.
    periodLabel: Optional[str] = None


@dataclass
class TrackerHeadlineMetric(APIModel):
    """Top-of-page stat tile. A tracker may have 0–N headline metrics."""

    label: str = ""
    value: Any = None
    unit: Optional[str] = None
    asOf: Optional[str] = None
    methodologyNote: Optional[str] = None
    trend: Optional[str] = None


@dataclass
class TrackerTableRow(APIModel):
    """One row of a ``viewType: "table"`` tracker (e.g. a leaderboard cell)."""

    rank: Optional[int] = None
    rowId: str = ""
    name: str = ""
    category: Optional[str] = None
    url: Optional[str] = None
    metrics: List[TrackerMetricValue] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "TrackerTableRow":
        if data is None:
            return None  # type: ignore[return-value]
        return cls(
            rank=data.get("rank"),
            rowId=data.get("rowId", ""),
            name=data.get("name", ""),
            category=data.get("category"),
            url=data.get("url"),
            metrics=[TrackerMetricValue.from_dict(m) for m in data.get("metrics", []) if m is not None],
        )


@dataclass
class TrackerGeoEntry(APIModel):
    """One geographic row for a ``viewType: "choropleth"`` tracker."""

    geoId: Optional[str] = None
    isoCode: Optional[str] = None
    fips: Optional[str] = None
    name: str = ""
    metrics: List[TrackerMetricValue] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "TrackerGeoEntry":
        if data is None:
            return None  # type: ignore[return-value]
        return cls(
            geoId=data.get("geoId"),
            isoCode=data.get("isoCode"),
            fips=data.get("fips"),
            name=data.get("name", ""),
            metrics=[TrackerMetricValue.from_dict(m) for m in data.get("metrics", []) if m is not None],
        )


@dataclass
class TrackerSnapshot(APIModel):
    """Standardized envelope every tracker returns. Exactly one of the payload
    fields (``rows``, ``geo``, ``timeSeries``) is populated based on ``viewType``;
    ``headline``, ``narrative`` are companion fields that may appear on any
    tracker. ``asOf`` is a free-form 'data as of' label (quarter, date, week)."""

    trackerId: str = ""
    scope: Optional[str] = None
    schemaVersion: str = ""
    displayName: str = ""
    description: Optional[str] = None
    viewType: str = ""
    asOf: Optional[str] = None
    generatedAt: Optional[str] = None
    generatedBy: Optional[str] = None
    narrative: Optional[str] = None
    headline: List[TrackerHeadlineMetric] = field(default_factory=list)
    geo: List[TrackerGeoEntry] = field(default_factory=list)
    rows: List[TrackerTableRow] = field(default_factory=list)
    # `timeSeries`, `events`, `signals`, `sources` aren't typed yet; they're
    # forward-compatible (Phase 3 trackers add them); access via .raw if needed.
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "TrackerSnapshot":
        if data is None:
            return None  # type: ignore[return-value]
        return cls(
            trackerId=data.get("trackerId", ""),
            scope=data.get("scope"),
            schemaVersion=data.get("schemaVersion", ""),
            displayName=data.get("displayName", ""),
            description=data.get("description"),
            viewType=data.get("viewType", ""),
            asOf=data.get("asOf"),
            generatedAt=data.get("generatedAt"),
            generatedBy=data.get("generatedBy"),
            narrative=data.get("narrative"),
            headline=[TrackerHeadlineMetric.from_dict(h) for h in (data.get("headline") or []) if h is not None],
            geo=[TrackerGeoEntry.from_dict(g) for g in (data.get("geo") or []) if g is not None],
            rows=[TrackerTableRow.from_dict(r) for r in (data.get("rows") or []) if r is not None],
            raw=data,
        )


# ── Indexes ─────────────────────────────────────────────────


@dataclass
class IndexListing(APIModel):
    """Per-index discovery row returned by ``client.list_indexes()``.

    ``canonicalUrl`` points at the *richest* view of the index, which is not
    always the detail route. Market Mood's entry points at ``/api/v2/market-mood``
    because that route carries a phase band, a weekly change, the per-signal
    breakdown and a per-sector map that the shared index envelope cannot hold.
    Every advertised ``indexId`` still resolves on ``client.get_index()``, so a
    generic client can iterate this listing without special-casing anything.
    """

    indexId: str = ""
    displayName: str = ""
    description: str = ""
    scale: str = ""  # "SENTIMENT" (signed, -1..+1) or "PERCENT_0_100"
    accessTier: str = ""  # "free" or "pro"; every index is "free" today
    canonicalUrl: str = ""


@dataclass
class IndexListResponse(APIModel):
    """Discovery envelope returned by ``client.list_indexes()``."""

    indexes: List[IndexListing] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "IndexListResponse":
        if data is None:
            return None  # type: ignore[return-value]
        return cls(indexes=[IndexListing.from_dict(i) for i in (data.get("indexes") or []) if i is not None])


@dataclass
class IndexConstituent(APIModel):
    """One entity's contribution to a basket index's headline value.

    ``staleness`` is ``FRESH`` (mentioned inside the lookback), ``CARRIED_FORWARD``
    (no mentions, last known value standing in), ``EXCLUDED`` (no usable reading,
    renormalized out), or ``OUT_OF_SEGMENT`` (not in the basket on this date, so
    ``weight`` is 0 and the row is present only for transparency).

    ``contribution`` is reserved by the API and currently returns ``None`` on
    every constituent. Do not build on it. To get the same number today, compute
    ``weight * value`` over the sum of ``weight`` across the constituents whose
    ``staleness`` is not ``EXCLUDED``.
    """

    kbEntityId: str = ""
    displayName: str = ""
    role: str = ""
    weight: float = 0.0
    value: Optional[float] = None
    mentionsCount: Optional[int] = None
    staleness: str = ""
    contribution: Optional[float] = None  # reserved; always None today
    link: Optional[str] = None


@dataclass
class IndexSnapshot(APIModel):
    """Latest reading for one index, returned by ``client.get_index()``.

    Two archetypes share this envelope, and the difference is load-bearing:

    * A **basket** index (``fed-sentiment``, ``ai-sentiment``) weight-averages
      tracked entities, so ``constituents``, ``basketSize``, ``coverage`` and
      ``totalMentions`` describe how the headline was built.
    * A **composite** index (``market-mood``) is built from signals rather than
      entities, so those four are ``None`` *by construction*, not because data is
      missing. Branch on them; do not treat ``None`` as an error.

    Compare ``coverage`` against ``basketSize`` on a basket index to spot a thin
    day before quoting the number.
    """

    indexId: str = ""
    displayName: str = ""
    asOf: str = ""  # YYYY-MM-DD; bucket start for weekly indexes
    value: Optional[float] = None
    scale: str = ""
    coverage: Optional[int] = None  # None on a composite index
    basketSize: Optional[int] = None  # None on a composite index
    totalMentions: Optional[int] = None  # None on a composite index
    methodologyNote: str = ""
    constituents: Optional[List[IndexConstituent]] = None  # None on a composite index

    @classmethod
    def from_dict(cls, data: dict) -> "IndexSnapshot":
        if data is None:
            return None  # type: ignore[return-value]
        known = {f.name for f in dataclasses.fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known and k != "constituents"}
        raw = data.get("constituents")
        # Preserve the None/[] distinction: None means "not a basket", [] means
        # "a basket with nothing in it today". Collapsing them loses the archetype.
        kwargs["constituents"] = (
            None if raw is None
            else [IndexConstituent.from_dict(c) for c in raw if c is not None]
        )
        return cls(**kwargs)


@dataclass
class IndexHistoryPoint(APIModel):
    """One point on an index's scalar series."""

    date: str = ""  # YYYY-MM-DD
    value: Optional[float] = None


@dataclass
class IndexHistoryResponse(APIModel):
    """Historical series returned by ``client.get_index_history()``.

    Point spacing follows the index, not the calendar: a weekly index emits one
    point per Monday-Sunday bucket, a daily index one per day, and Market Mood
    trading days only. Thin or low-coverage buckets are withheld rather than
    published, so ``history`` can be shorter than ``days`` and can contain gaps.
    Plot against ``date``; never assume a fixed interval, and never read a
    missing date as zero.
    """

    indexId: str = ""
    displayName: str = ""
    scale: str = ""
    days: int = 0
    history: List[IndexHistoryPoint] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "IndexHistoryResponse":
        if data is None:
            return None  # type: ignore[return-value]
        return cls(
            indexId=data.get("indexId", ""),
            displayName=data.get("displayName", ""),
            scale=data.get("scale", ""),
            days=data.get("days", 0),
            history=[IndexHistoryPoint.from_dict(p) for p in (data.get("history") or []) if p is not None],
        )


# ── Screener ─────────────────────────────────────────────────


@dataclass
class ScreenerFieldOption(APIModel):
    """One selectable value of an ``ENUM`` screener field.

    ``value`` is the number a filter carries; ``label`` is display copy.
    """

    value: Optional[float] = None
    label: str = ""


@dataclass
class ScreenerField(APIModel):
    """One filterable field from ``client.get_screener_fields()``.

    Build a filter UI from this rather than hardcoding the field list, and new
    fields appear without a client release.

    ``type`` is ``NUMBER``, ``ENUM`` or ``STRING``:

    * ``NUMBER`` takes a scalar ``value`` and the comparison ops in ``ops``.
    * ``ENUM`` is an ordinal with a fixed set of readings; ``options`` carries
      them and ``ops`` is ``["EQ"]``.
    * ``STRING`` (ETF universe only) takes ``IN`` / ``NOT_IN`` against a
      ``values`` list, which is populated from the live universe rather than a
      static list, so the pickers stay current.

    ``quickValues`` are the thresholds worth offering as one-tap presets: on the
    SentiSense Score fields those are the band edges (5, 13, 23).
    """

    name: str = ""
    label: str = ""
    group: str = ""
    type: str = ""
    unit: Optional[str] = None
    ops: List[str] = field(default_factory=list)
    sortable: bool = False
    step: Optional[float] = None
    placeholder: Optional[str] = None
    description: str = ""
    options: Optional[List[ScreenerFieldOption]] = None  # ENUM fields only
    quickValues: Optional[List[str]] = None
    values: Optional[List[str]] = None  # STRING fields only

    @classmethod
    def from_dict(cls, data: dict) -> "ScreenerField":
        if data is None:
            return None  # type: ignore[return-value]
        known = {f.name for f in dataclasses.fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known and k != "options"}
        raw = data.get("options")
        kwargs["options"] = (
            None if raw is None
            else [ScreenerFieldOption.from_dict(o) for o in raw if o is not None]
        )
        return cls(**kwargs)


@dataclass
class ScreenerFieldCatalog(APIModel):
    """Both field catalogs, returned by ``client.get_screener_fields()``.

    ``stock`` backs ``run_screen()``; ``etf`` backs ``run_etf_screen()``. The two
    universes do not share a field vocabulary, so a name from one is not valid
    in the other.
    """

    stock: List[ScreenerField] = field(default_factory=list)
    etf: List[ScreenerField] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "ScreenerFieldCatalog":
        if data is None:
            return None  # type: ignore[return-value]
        return cls(
            stock=[ScreenerField.from_dict(f) for f in (data.get("stock") or []) if f is not None],
            etf=[ScreenerField.from_dict(f) for f in (data.get("etf") or []) if f is not None],
        )


@dataclass
class FeaturedScreen(APIModel):
    """A curated screen, returned by ``client.list_screens()``.

    ``plan`` is left as a plain dict so it round-trips straight back into
    ``run_screen(screen.plan)`` (or ``run_etf_screen`` when
    ``plan["universe"] == "ETF"``) with nothing to rebuild.

    ``id`` is stable and safe to persist. ``name`` and ``summary`` are display
    copy and may be revised.
    """

    id: str = ""
    name: str = ""
    summary: str = ""
    plan: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScreenerRow(APIModel):
    """One matching stock, with the full field set rather than only the fields
    you filtered on, so you can sort or post-process without a second call.

    A field with no data for that ticker is ``None``, and a row missing the
    field you filtered on never matches: ``RETURN_1Y >= 0`` and
    ``RETURN_1Y < 0`` do not partition the universe.

    ``sentiSenseScore7D`` / ``sentiSenseScore1M`` are the SentiSense Score, not
    sentiment polarity: unbounded, banded at 5 / 13 / 23 either side of zero.
    ``sentimentDirection`` is that Score's side of the neutral band (``1`` /
    ``0`` / ``-1``), and ``maCrossState`` is ordinal (``1`` golden cross, ``-1``
    death cross, ``0`` neither), so compare both with ``EQ``.
    ``analystRatingMean`` runs the vendor's 1-to-5 scale where **1.0 is strong
    buy**; prefer ``analystBuyRatioPct``, which runs the intuitive direction.
    """

    ticker: str = ""
    sentiSenseScore7D: Optional[float] = None
    sentiSenseScore1M: Optional[float] = None
    scoreChange7D: Optional[float] = None
    sentimentDirection: Optional[float] = None  # 1 / 0 / -1
    socialDominance: Optional[float] = None
    mentionShare: Optional[float] = None
    mentionVelocity: Optional[float] = None
    dominanceChange: Optional[float] = None
    marketCap: Optional[int] = None
    currentPrice: Optional[float] = None
    changePercent: Optional[float] = None
    change: Optional[float] = None
    volume: Optional[int] = None
    week52High: Optional[float] = None
    week52Low: Optional[float] = None
    pctOff52wHigh: Optional[float] = None
    pctOff52wLow: Optional[float] = None
    analystBuyRatioPct: Optional[float] = None
    analystTargetUpsidePct: Optional[float] = None
    analystCount: Optional[float] = None
    analystRatingMomentum30D: Optional[float] = None
    analystRatingMean: Optional[float] = None  # INVERTED: 1.0 is strong buy
    pctOff200dMa: Optional[float] = None
    pctOff50dMa: Optional[float] = None
    maCrossState: Optional[float] = None  # 1 golden, -1 death, 0 neither
    return1M: Optional[float] = None
    return3M: Optional[float] = None
    return6M: Optional[float] = None
    return1Y: Optional[float] = None
    volatility30D: Optional[float] = None
    sentisenseScoreBars7D: Optional[List[float]] = None
    sentisenseScoreBars30D: Optional[List[float]] = None
    priceSparkline30D: Optional[List[float]] = None
    lastUpdated: Optional[int] = None  # epoch seconds


@dataclass
class EtfScreenerRow(APIModel):
    """One matching fund, with the full ETF field set.

    The two Score readings answer different questions.
    ``constituentsWeightedSentisense`` is the holdings-weighted SentiSense Score
    across what the fund actually owns, which is usually the one you want;
    ``directSentisense`` is the Score from chatter about the fund ticker itself,
    which on a broad index fund is mostly macro noise.

    ``weightCoveredPct`` is how much of the fund's weight had constituent data
    behind the weighted number, so read it before quoting that number.
    """

    ticker: str = ""
    name: str = ""
    issuer: Optional[str] = None
    assetClass: Optional[str] = None
    trackedIndex: Optional[str] = None
    marketCap: Optional[int] = None  # AUM in USD
    expenseRatio: Optional[float] = None  # percent points: 0.09 means 0.09%
    currentPrice: Optional[float] = None
    changePercent: Optional[float] = None
    priceChange: Optional[float] = None
    volume: Optional[int] = None
    week52High: Optional[float] = None
    week52Low: Optional[float] = None
    pctOff52wHigh: Optional[float] = None
    pctOff52wLow: Optional[float] = None
    weightedAnalystUpside: Optional[float] = None
    weightedConsensusLabel: Optional[str] = None
    weightedInsiderNet30d: Optional[int] = None
    weightedInsiderNet90d: Optional[int] = None
    constituentsWeightedSentisense: Optional[float] = None
    directSentisense: Optional[float] = None
    weightCoveredPct: Optional[float] = None
    holdingsCount: Optional[int] = None
    totalKnownHoldings: Optional[int] = None
    partial: Optional[bool] = None
    lastUpdated: Optional[int] = None  # epoch seconds


@dataclass
class ScreenerResults(APIModel):
    """Stock screen results, returned by ``client.run_screen()``.

    ``matched`` is how many rows the plan matched *before* ``limit`` was
    applied, so truncation is visible: when ``matched`` exceeds ``limit`` you
    are looking at the top slice under the plan's sort, not the whole answer.
    """

    results: List[ScreenerRow] = field(default_factory=list)
    matched: int = 0
    limit: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "ScreenerResults":
        if data is None:
            return None  # type: ignore[return-value]
        return cls(
            results=[ScreenerRow.from_dict(r) for r in (data.get("results") or []) if r is not None],
            matched=data.get("matched", 0),
            limit=data.get("limit", 0),
        )


@dataclass
class EtfScreenerResults(APIModel):
    """ETF screen results, returned by ``client.run_etf_screen()``.

    Same envelope as :class:`ScreenerResults`; ``matched`` is the pre-limit
    count.
    """

    results: List[EtfScreenerRow] = field(default_factory=list)
    matched: int = 0
    limit: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "EtfScreenerResults":
        if data is None:
            return None  # type: ignore[return-value]
        return cls(
            results=[EtfScreenerRow.from_dict(r) for r in (data.get("results") or []) if r is not None],
            matched=data.get("matched", 0),
            limit=data.get("limit", 0),
        )
