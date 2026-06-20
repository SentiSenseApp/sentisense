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
    ``.preview_reason`` for tier information. On preview list responses
    ``.total_count`` is the number of items in the full PRO dataset, so you can
    show "showing N of total_count" (``None`` on full PRO responses).

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
    """Real-time stock price data.

    ``currentPrice`` is always the regular-session price (live last trade during RTH,
    most recent regular-session close otherwise). ``extendedHours`` is populated only
    during pre-market or after-hours sessions.
    """

    ticker: str = ""
    currentPrice: float = 0.0
    change: float = 0.0
    changePercent: float = 0.0
    previousClose: float = 0.0
    volume: int = 0
    timestamp: int = 0
    extendedHours: Optional[ExtendedHoursInfo] = None


@dataclass
class StockQuote(APIModel):
    """Aggregate quote snapshot from GET /api/v1/stocks/{ticker}/quote.

    Combines live price, today OHLC, 52-week range, market cap, and key
    fundamentals into a single payload. All fields except ``ticker`` may be
    ``None`` when the upstream data source is unavailable.

    ``currentPrice`` is always the regular-session price. ``extendedHours`` is
    populated only during pre-market or after-hours sessions; see
    :class:`ExtendedHoursInfo` for the nested shape.
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
    timestamp: Optional[int] = None
    extendedHours: Optional[ExtendedHoursInfo] = None


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
    """Stock with company name and entity metadata."""

    ticker: str = ""
    name: str = ""
    kbEntityId: Optional[str] = None
    urlSlug: Optional[str] = None


@dataclass
class MarketStatus(APIModel):
    """Market open/closed status."""

    status: str = ""  # "open" or "closed"
    timestamp: int = 0


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
    transactionCode: str = ""
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
    transactionType: str = ""
    transactionDate: str = ""
    disclosureDate: str = ""
    amountRange: str = ""
    amountMin: int = 0
    amountMax: int = 0
    owner: str = ""
    urlSlug: str = ""
    imageUrl: Optional[str] = None
    assetType: Optional[str] = None
    disclosureDelayDays: Optional[int] = None
    sentiSenseScore: Optional[float] = None


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
    type: str = ""  # "News", "X", "Reddit", etc.


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
    displayTickers: List[str] = field(default_factory=list)
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

    totalMentions: int = 0
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
    activistActivity: bool = False
    reportDate: str = ""
    # Quarterly average closing price used to weight the dollar flow. None when no
    # price is cached for this (quarter, ticker) yet.
    avgClosePrice: Optional[float] = None
    # Dollar-weighted net flow: netSharesChange × avgClosePrice. 0 when avgClosePrice
    # is missing — clients should fall back to displaying netSharesChange.
    dollarFlowUsd: float = 0.0


@dataclass
class InstitutionalFlows(APIModel):
    """Market flows split into inflows and outflows."""

    inflows: List[InstitutionalFlow] = field(default_factory=list)
    outflows: List[InstitutionalFlow] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "InstitutionalFlows":
        return cls(
            inflows=[InstitutionalFlow.from_dict(f) for f in data.get("inflows", [])],
            outflows=[InstitutionalFlow.from_dict(f) for f in data.get("outflows", [])],
        )


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
    as of 2026-05-15 — limited fund coverage; expect 404 for funds outside the
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
# Trackers are observational data products. Every tracker — institution-alpha
# leaderboards, hedge-fund reported returns, social trackers, surveillance
# dashboards — returns the same standardized `TrackerSnapshot` envelope.
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
    # `timeSeries`, `events`, `signals`, `sources` aren't typed yet — they're
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
