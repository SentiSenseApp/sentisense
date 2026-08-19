# SentiSense Python SDK

[![PyPI version](https://img.shields.io/pypi/v/sentisense.svg)](https://pypi.org/project/sentisense/)
[![Python versions](https://img.shields.io/pypi/pyversions/sentisense.svg)](https://pypi.org/project/sentisense/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Official Python SDK for the [SentiSense](https://sentisense.ai) market intelligence API.

## Installation

```bash
pip install sentisense
```

## Quick Start

```python
from sentisense import SentiSenseClient

client = SentiSenseClient("your-api-key")

# The tracked universe: every ticker SentiSense covers
tickers = client.get_all_stocks()          # ["A", "AAL", "AAPL", ...]
print(len(tickers), "stocks tracked")

# Same universe with company names and knowledge base entity ids
detailed = client.get_all_stocks_detailed()
print(detailed[0].ticker, detailed[0].simpleName, detailed[0].kbEntityId)

# Get a stock price
price = client.get_stock_price("AAPL")
print(price)

# Get multiple stock prices
prices = client.get_stock_prices(["AAPL", "MSFT", "GOOGL"])

# Check market status
status = client.get_market_status()
print(status)

# Get latest news for a stock
news = client.get_documents_by_ticker("TSLA", source="news", days=7)

# Search across news and social media
results = client.search_documents("AI earnings surprise")

# Get mention time series for a stock (v2 metrics API)
mentions = client.get_metrics("NVDA", metric_type="mentions")

# Get sentiment polarity time series, each reading in [-1, 1]
sentiment = client.get_metrics("NVDA", metric_type="sentiment")

# Get the SentiSense Score time series: sentiment weighted by attention, unbounded
score = client.get_metrics("NVDA", metric_type="sentisense_score")
print(score[-1]["value"])   # latest reading, e.g. 51.3

# Get mentions broken down by source
dist = client.get_metrics_distribution("NVDA", metric_type="mentions", dimension="source")
```

## Authentication

All API requests require an API key. You can generate one from your [Developer Console](https://app.sentisense.ai/settings/developer).

```python
client = SentiSenseClient("your-api-key")
```

For full endpoint documentation, request/response schemas, and interactive examples, see the [API Documentation](https://sentisense.ai/docs/api/).

## API Reference

### Stocks

| Method | Description |
|--------|-------------|
| `get_stock_price(ticker)` | Real-time price for a single stock |
| `get_stock_prices(tickers)` | Real-time prices for multiple stocks |
| `get_stock_profile(ticker)` | Company profile |
| `get_stock_entities(ticker)` | Tracked entities related to a stock (executives, products) |
| `get_stock_ai_summary(ticker, depth="basic")` | Curated AI research report. `depth="deep"` returns the full report and consumes one report view |
| `get_stock_chart(ticker, timeframe="1M")` | OHLCV chart data, returned as a bare list of bars (oldest first) |
| `get_all_stocks()` | The tracked universe: every ticker SentiSense covers |
| `get_all_stocks_detailed()` | The same universe with company names, entity IDs and social dominance |
| `get_market_status()` | Market open/closed status |
| `get_fundamentals(ticker, timeframe="quarterly")` | Financial fundamentals |
| `get_current_fundamentals(ticker)` | Most recent fundamentals snapshot |
| `get_historical_revenue(ticker)` | Historical revenue series |
| `get_short_interest(ticker)` | Short interest (FINRA bi-monthly) |
| `get_float(ticker)` | Shares float |
| `get_short_volume(ticker)` | Daily short-sale volume (FINRA) |

### Knowledge Base

| Method | Description |
|--------|-------------|
| `get_popular_kb_entities()` | Popular KB entities (search suggestions) |

### News & Documents

| Method | Description |
|--------|-------------|
| `get_documents_by_ticker(ticker, source?, days?, hours?, limit?)` | News and social posts for a stock |
| `get_documents_by_ticker_range(ticker, start_date, end_date)` | Documents within a date range |
| `get_documents_by_entity(entity_id)` | Documents for a KB entity |
| `search_documents(query, source?, days?, limit?)` | Natural language search across news and social |
| `get_documents_by_source(source, days?, hours?, limit?)` | Latest from a source ("news", "reddit", "x", "substack") |
| `get_stories(limit?, days?, expanded?)` | AI-curated news story clusters |
| `get_stories_by_ticker(ticker, limit?)` | Stories for a specific stock |

### Metrics (v2)

| Method | Description |
|--------|-------------|
| `get_metrics(symbol, metric_type="sentiment", start_time?, end_time?, max_data_points?)` | Time series for a metric (mentions, sentiment, sentisense_score, social_dominance, creators) |
| `get_metrics_distribution(symbol, metric_type="mentions", dimension="source", start_time?, end_time?)` | Metric distribution by dimension (e.g. mentions by source) |

> **Note:** `start_time` and `end_time` are epoch milliseconds.

### Institutional Flows (13F)

| Method | Description |
|--------|-------------|
| `get_institutional_quarters()` | Available 13F reporting quarters |
| `get_institutional_flows(report_date=None, limit=50)` | Fund flows for a quarter (omit `report_date` for the latest) |
| `get_stock_holders(ticker, report_date, limit=None, offset=None, sort_by=None, sort_dir=None)` | Institutional holders for a stock (see paging note below) |
| `get_activist_positions(report_date)` | Activist investor positions |

#### Paging the holder list

A widely held ticker returns thousands of rows: a megacap quarter is roughly 6,000
holders and 1.5 MB on the wire. Pass `limit` unless you really want the whole list.
Omitting every paging argument sends the original unbounded request, so existing code
keeps working.

| Argument | Values |
|----------|--------|
| `limit` | Maximum rows to return. Must be >= 1; values above 1000 are capped server-side. Omit for the full list. |
| `offset` | Row offset to start from, used with `limit`. Server default is 0. |
| `sort_by` | `"shares"` (server default), `"valueUsd"`, or `"sharesChangePct"`. |
| `sort_dir` | `"desc"` (server default) or `"asc"`. |

```python
import os
from sentisense import SentiSenseClient

client = SentiSenseClient(os.environ["SENTISENSE_API_KEY"])

# Top 10 holders by position value, largest first
top = client.get_stock_holders(
    "AAPL", "2026-03-31", limit=10, sort_by="valueUsd", sort_dir="desc"
)
for holder in top.holders:
    print(holder["filerName"], holder["valueUsd"])

# Walk the list a page at a time
page = client.get_stock_holders("AAPL", "2026-03-31", limit=100, offset=100)
print(f"{page.returnedCount} rows from offset {page.offset} of {page.holderCount}")
```

Paged responses carry `returnedCount` and `offset` next to the holder rows, so you can
walk the list without re-counting it yourself.

### Analyst Ratings

The **price target cone** (mean, high, low, upside %) and consensus are **free for everyone, full data via API**: we give it away. Upgrade/downgrade feeds and forward EPS estimates are limited on free, unlimited on PRO.

| Method | Description |
|--------|-------------|
| `get_analyst_consensus(ticker)` | Price target band (mean, high, low), analyst count, upside %. Free for everyone, full data. |
| `get_analyst_actions(ticker, lookback_days=90)` | Recent upgrade/downgrade actions. Free: 3 most recent. PRO: unlimited. |
| `get_analyst_estimates(ticker)` | Forward EPS estimates and earnings surprise history. Free: 1 quarter. PRO: full history. |
| `get_analyst_market_activity(lookback_days=30)` | Market-wide recent analyst actions across all tickers (PRO). |

### Company KPIs (PRO)

| Method | Description |
|--------|-------------|
| `get_company_kpis(ticker)` | Company-specific KPI time-series (product metrics, segment revenue). Free tier returns metadata only (empty `kpis` array); PRO returns full series. |
| `list_kpi_coverage()` | List all tickers with curated KPI coverage (free, no quota cost) |

### Earnings

The earnings analysis report is the assembled version of a quarter: one object per fiscal period carrying the editorial headline, the KPI cards with year-over-year deltas, the guidance language as management phrased it, and a summary of the earnings call. Pair it with the recent-reporters feed to drive a post-earnings sweep.

| Method | Description |
|--------|-------------|
| `get_earnings_summaries(ticker, limit=None)` | Per-quarter earnings analysis report, newest first. FREE: the latest quarter, shaped (section titles and a guidance direction, no bodies). PRO: every hydrated quarter in full. |
| `get_recent_earnings(days=None, limit=None)` | Which covered companies reported in a recent window, newest first. Full window on every key. |

```python
import os

from sentisense import SentiSenseClient

client = SentiSenseClient(os.environ["SENTISENSE_API_KEY"])

result = client.get_earnings_summaries("AAPL", limit=1)
if result.data:
    quarter = result.data[0]
    print(quarter.fiscalPeriod, quarter.reportDate)
    print(quarter.headline)
    for kpi in quarter.kpiHighlights:
        print(f"  {kpi.label}: {kpi.value} ({kpi.yoy or 'no YoY'})")

    if result.is_preview:
        # Free key: section titles stand in for the bodies.
        print("Summary covers:", ", ".join(quarter.summaryTopics))
    else:
        print(quarter.summaryMd)
```

### ETFs (beta)

Composition data is public; the holdings-weighted aggregate views follow the same PRO-with-preview pattern as Analyst/Insider. Aggregates synthesize fund-level views from each constituent's per-stock data (analyst coverage, insider trades, sentiment), weighted by allocation. Every aggregate response carries a `coverage` block so you see exactly how much of the fund's AUM the underlying data covered.

| Method | Description |
|--------|-------------|
| `list_etfs()` | Every ETF tracked by SentiSense. Returns ticker, fund name, issuer, tracked index, asset class. |
| `get_etf_holdings(ticker)` | Full composition: per-holding weights and freshness metadata. |
| `get_etf_analyst_aggregate(ticker)` | Holdings-weighted analyst consensus (weighted upside, distribution). Free: headline + coverage. PRO: + `topContributors`. |
| `get_etf_insider_aggregate(ticker, lookback_days=30)` | Holdings-weighted Form 4 net flow over a configurable window. Free: headline + buy/sell split. PRO: + `topContributors`. |
| `get_etf_sentiment_aggregate(ticker)` | Two SentiSense readings side-by-side: constituent-weighted and direct (mentions of the fund itself). |

### Screener

Filter the tracked universe on the SentiSense Score, attention, analyst consensus, technicals and price in one query. Screening on analyst ratings alone is something a dozen free tools do; screening on analyst ratings *where the Score disagrees* is not.

| Method | Description |
|--------|-------------|
| `get_screener_fields()` | Every filterable field, with units, operators and descriptions, for both universes |
| `list_screens()` | The curated screens shipped in the product, each with a runnable plan |
| `run_screen(plan, tickers=None, limit=None)` | Run a screen against the stock universe |
| `run_etf_screen(plan, tickers=None, limit=None)` | Run a screen against the ETF universe |

```python
import os
from sentisense import SentiSenseClient

client = SentiSenseClient(os.environ["SENTISENSE_API_KEY"])

# Run a curated screen as-is
screen = next(s for s in client.list_screens() if s.id == "crowd-vs-street")
res = client.run_screen(screen.plan, limit=25)
print(f"{res.matched} matched, showing {len(res.results)}")

# Or build your own: bullish Score, thin analyst enthusiasm
res = client.run_screen(
    {
        "filters": [
            {"fieldName": "SENTI_SCORE_7D", "op": "GTE", "value": 13},
            {"fieldName": "ANALYST_BUY_RATIO_PCT", "op": "LTE", "value": 30},
            {"fieldName": "ANALYST_COUNT", "op": "GTE", "value": 5},
        ],
        "sort": {"fieldName": "SENTI_SCORE_7D", "dir": "DESC"},
    },
    limit=25,
)
for row in res.results:
    print(row.ticker, row.sentiSenseScore7D, row.analystBuyRatioPct)
```

`limit` rides next to the plan rather than inside it, because a plan is a stored object and paging is a transport concern. It defaults to 100 and caps at 500. `matched` is the count before `limit` was applied, so truncation is visible. `tickers` is optional: omit it to screen the whole tracked universe, pass a list to screen a watchlist.

Three field semantics are worth stating outright, because guessing them wrong produces a screen that looks fine and means nothing:

- **`ANALYST_RATING_MEAN` is inverted.** It is the vendor's 1-to-5 scale where **1.0 is strong buy**, so bullish is `LTE 2.5`. Prefer `ANALYST_BUY_RATIO_PCT`, which runs the intuitive direction.
- **`MA_CROSS_STATE` is ordinal**, not a percentage: `1` golden cross, `-1` death cross, `0` neither. Use `EQ`.
- **`SENTIMENT_DIRECTION` is the sign of the 7-day SentiSense Score** (`1` / `0` / `-1`) with a neutral band of plus-or-minus 5. Despite the name it is not sentiment polarity, and `0` matches only an exact zero.

The Score fields (`SENTI_SCORE_7D`, `SENTI_SCORE_1M`, `SCORE_CHANGE_7D`) are the SentiSense Score, not polarity: unbounded, banded at 5 / 13 / 23 either side of zero. Filter on those band edges, not on values like `0.5`, which behave as "any positive score". Nulls never match in either direction, so `RETURN_1Y >= 0` and `RETURN_1Y < 0` do not partition the universe: a stock listed four months ago is in neither result. If a screen returns fewer rows than you expect, check coverage before you check your thresholds.

Screens read a snapshot that refreshes every 20 minutes, so this is not a quote feed. Use `get_stock_price` for live prices.

## Error Handling

The SDK raises typed exceptions for API errors:

```python
from sentisense import SentiSenseClient, AuthenticationError, RateLimitError

client = SentiSenseClient("your-api-key")

try:
    price = client.get_stock_price("AAPL")
except AuthenticationError:
    print("Invalid or missing API key")
except RateLimitError:
    print("Rate limit exceeded, try again later")
```

| Exception | HTTP Status | Description |
|-----------|-------------|-------------|
| `AuthenticationError` | 401, 403 | Invalid or missing API key |
| `NotFoundError` | 404 | Resource not found |
| `RateLimitError` | 429 | Rate limit exceeded |
| `DeepHistoryUnavailable` | 202 | Deep chart history (`10Y`, `MAX`) is still being assembled; retry shortly |
| `APIError` | Other 4xx/5xx | General API error |

All exceptions inherit from `SentiSenseError` and include `.status_code`, `.message`, and `.response` attributes.

## Not yet in the Python SDK

A few endpoints available in the Node SDK are intentionally not yet exposed here
(low-traffic / discovery-convenience surfaces). Call them directly over HTTP if you
need them: `/api/v1/stocks/images`, `/api/v1/stocks/descriptions`,
`/api/v1/stocks/popular`, `/api/v1/documents/stories/{clusterId}` (single-story
detail), and the metrics breakdown endpoint.

## License

MIT - see [LICENSE](LICENSE) for details.
