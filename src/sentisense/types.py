"""Typed response models for the SentiSense API.

All models support both attribute access (``price.ticker``) and dict-style
access (``price["ticker"]``) for backward compatibility.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Generic, Iterator, List, Optional, TypeVar

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

    Access the underlying data directly via attribute or item access.
    Check ``.is_preview`` and ``.preview_reason`` for tier information.
    """

    def __init__(self, data: T, is_preview: bool, preview_reason: Optional[str]):
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "is_preview", is_preview)
        object.__setattr__(self, "preview_reason", preview_reason)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._data, name)

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
class StockPrice(APIModel):
    """Real-time stock price data."""

    ticker: str = ""
    currentPrice: float = 0.0
    change: float = 0.0
    changePercent: float = 0.0
    previousClose: float = 0.0
    volume: int = 0
    timestamp: int = 0


@dataclass
class StockQuote(APIModel):
    """Aggregate quote snapshot from GET /api/v1/stocks/{ticker}/quote.

    Combines live price, today OHLC, 52-week range, market cap, and key
    fundamentals into a single payload. All fields except ``ticker`` may be
    ``None`` when the upstream data source is unavailable.
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
    extendedHours: Optional[bool] = None


@dataclass
class SimilarStock(APIModel):
    """Peer/similar stock with optional price data."""

    symbol: str = ""
    name: str = ""
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
    createdAt: int = 0


@dataclass
class Story(APIModel):
    """AI-curated news story with impact score and tickers."""

    cluster: Optional[StoryCluster] = None
    displayTickers: List[str] = field(default_factory=list)
    tickers: List[str] = field(default_factory=list)
    impactScore: float = 0.0
    brokeAt: int = 0
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


# ── KPI types ( / ) ─────────────────────────


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
