# SentiSense Python SDK

[![PyPI version](https://img.shields.io/pypi/v/sentisense.svg)](https://pypi.org/project/sentisense/)
[![Python versions](https://img.shields.io/pypi/pyversions/sentisense.svg)](https://pypi.org/project/sentisense/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Official Python SDK for the [SentiSense](https://sentisense.ai) market intelligence API: stock prices and fundamentals, news and social sentiment, the SentiSense Score, insider and congressional trading, institutional 13F flows, analyst ratings, earnings analysis, ETF aggregates, and a cross-signal screener.

- Typed dataclasses for every response, each one still readable with dict-style access
- One flat client, so there are no resource namespaces to learn
- Tier-gated responses are unwrapped for you, so preview and full data read the same way
- Automatic retries on rate limits and on deep chart history, plus a typed exception hierarchy
- Ships `py.typed`, supports Python 3.8 and up, and depends only on `requests`

Get a free API key at [app.sentisense.ai/get-api-key](https://app.sentisense.ai/get-api-key). Full API docs at [sentisense.ai/docs/api](https://sentisense.ai/docs/api/).

## Contents

- [Install](#install)
- [Quick Start](#quick-start)
- [Authentication and Configuration](#authentication-and-configuration)
- [Response Shapes](#response-shapes)
- [API Reference](#api-reference)
- [Error Handling](#error-handling)

## Install

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

# Latest price for one stock, and for several
price = client.get_stock_price("AAPL")
print(price.currentPrice, price.changePercent)
prices = client.get_stock_prices(["AAPL", "MSFT", "GOOGL"])

# Is the market open right now
status = client.get_market_status()

# Latest news for a stock, and a search across news and social
news = client.get_documents_by_ticker("TSLA", source="news", days=7)
results = client.search_documents("AI earnings surprise")
for doc in results.documents:
    print(doc.url, doc.averageSentiment)

# Mention volume over time (v2 metrics API)
mentions = client.get_metrics("NVDA", metric_type="mentions")

# Sentiment polarity over time, each reading in [-1, 1]
sentiment = client.get_metrics("NVDA", metric_type="sentiment")

# The SentiSense Score: sentiment weighted by attention, unbounded
score = client.get_metrics("NVDA", metric_type="sentisense_score")
print(score[-1]["value"])   # latest reading, e.g. 51.3

# Mentions broken down by source
dist = client.get_metrics_distribution("NVDA", metric_type="mentions", dimension="source")
```

## Authentication and Configuration

Every endpoint requires an API key. Generate one from the [Developer Console](https://app.sentisense.ai/get-api-key).

```python
import os
from sentisense import SentiSenseClient

client = SentiSenseClient(
    os.environ["SENTISENSE_API_KEY"],   # Get yours at app.sentisense.ai/get-api-key
    base_url="https://app.sentisense.ai",
    timeout=30.0,
    max_retries=3,
)
```

| Argument | Default | What it does |
|----------|---------|--------------|
| `api_key` | required, positional | Sent as the `X-SentiSense-API-Key` header on every request. |
| `base_url` | `https://app.sentisense.ai` | Override for a non-production host. |
| `timeout` | `30.0` | Per-request timeout in seconds. |
| `max_retries` | `3` | Retries on 429 and 5xx. Set `0` to fail fast. |

All three options are keyword-only. Retries honour a `Retry-After` header when the server sends one, clamped so an oversized value cannot wedge the calling thread, and fall back to exponential backoff with jitter otherwise. Since this client is synchronous, a retry blocks the thread that called it.

Keep the key in the environment rather than in source. Committing a literal key leaks it into git history and into every registry security scan that reads your repo.

## Response Shapes

Most methods hand back the payload directly. Two families wrap it, and one of the two is a proxy that mostly lets you forget it is there.

**1. Tier-gated endpoints return a `PreviewResult`.** The payload is in `.data`, `.is_preview` says whether your tier saw a truncated view, `.preview_reason` says why, and `.total_count` is the size of the full set behind the response. It is a transparent proxy, so you can also iterate it, index it, and read the payload's own attributes straight off the wrapper.

```python
# Object-wrapped: attribute access reads through to the payload
flows = client.get_institutional_flows()
print(flows.reportDate, len(flows.inflows))
for flow in flows.data.inflows:
    print(flow.ticker, flow.netSharesChange)

# List-wrapped: iterate the result, or read .data
trades = client.get_insider_trades("NVDA")
for trade in trades:
    print(trade.insiderName, trade.transactionCode, trade.sharesTransacted)
print(f"showing {len(trades)} of {trades.total_count}")

if trades.is_preview:
    print("Upgrade for the full history:", trades.preview_reason)
```

On a preview, `.total_count` is the size of the untruncated dataset, so you can render "showing N of total". On a paged endpoint it is the size of the whole matching set on every tier, PRO included, so compare it against the page you were handed to decide whether to fetch the next `offset`. It is `None` only on endpoints that return everything and therefore have no page to count past, never as a way of saying zero.

**2. Document endpoints return a `DocumentSearchResponse`.** This is not the preview envelope: the rows are in `.documents`, alongside `.totalCount` and the echoed query window, and there is no `is_preview`.

```python
results = client.search_documents("NVDA earnings", days=7)
print(f"{results.totalCount} matches")
for doc in results.documents:
    print(doc.url, doc.source, doc.averageSentiment)
```

Affected: `get_documents_by_ticker`, `get_documents_by_ticker_range`, `get_documents_by_entity`, `search_documents` and `get_documents_by_source`.

**3. Everything else returns the value itself**, including `get_stock_price`, `get_stock_chart`, `get_stories` and `get_institutional_quarters`. The two discovery methods, `list_institutions` and `get_politician_directory`, return the plain payload dictionary rather than a wrapper.

Every typed dataclass also supports dict-style access, so `price["currentPrice"]` and `price.currentPrice` both work and code written against an earlier untyped release keeps running.

## API Reference

### Stocks

| Method | Description |
|--------|-------------|
| `get_stock_price(ticker)` | Latest price for a single stock, delayed 15 minutes |
| `get_stock_prices(tickers)` | Latest prices for several stocks in one call |
| `get_stock_quote(ticker)` | Fuller snapshot: day OHLC, 52-week range, market cap, P/E, EPS TTM, dividend yield |
| `get_stock_profile(ticker)` | Company profile |
| `get_stock_entities(ticker)` | Tracked entities related to a stock (executives, products, organizations) |
| `get_similar_stocks(ticker, limit=5)` | Peer stocks with their current prices |
| `get_stock_ai_summary(ticker, depth="basic")` | Curated AI research report. `depth="deep"` returns the full report and consumes one report view |
| `get_stock_chart(ticker, timeframe="1M")` | OHLCV bars, returned as a bare list, oldest first |
| `get_all_stocks()` | The tracked universe: every ticker SentiSense covers |
| `get_all_stocks_detailed()` | The same universe with company names, entity ids and social dominance |
| `get_market_status()` | Market open or closed |

Price fields carry `priceAsOf` in Unix milliseconds for the age of the market data. Read that for freshness rather than `timestamp`, which records when the response was served and therefore always reads as now. During pre-market and after-hours a nested `extendedHours` object appears next to the regular-session price.

Chart timeframes are `1D`, `5D`, `1W`, `1M`, `3M`, `6M`, `1Y`, `5Y`, `10Y` and `MAX` (`ALL` is a legacy alias of `5Y`). Only `10Y` and `MAX` are dividend-adjusted; `5Y` and shorter are split-adjusted only, so do not compare a `10Y` close against a `1Y` close for the same day. Deep ranges answer `202` the first time a rarely-requested stock is asked for, which the SDK retries for you (see [Error Handling](#error-handling)).

### Fundamentals

| Method | Description |
|--------|-------------|
| `get_fundamentals(ticker, timeframe="quarterly")` | Income statement, balance sheet and cash flow, as filed |
| `get_current_fundamentals(ticker)` | Most recent fundamentals snapshot |
| `get_fundamentals_periods(ticker)` | Available SEC reporting periods with fiscal labels, for driving a period picker |
| `get_historical_revenue(ticker)` | Historical revenue series |
| `get_short_interest(ticker)` | Short interest, from bi-monthly settlement data |
| `get_float(ticker)` | Shares available for public trading |
| `get_short_volume(ticker)` | Daily short-sale volume, distinct from short interest |

Statement figures are reported in the filer's own currency, named by `reportedCurrency`, and are never converted to US dollars. An absent key means the currency is unknown, not that it is USD. For non-USD filers the API serves `peRatio`, `psRatio` and `pbRatio` as `None` on purpose, because a USD share price over a home-currency per-share figure is a unit mismatch; do not recompute them client-side.

Cash flow keys are `operatingCashFlow`, `investingCashFlow`, `financingCashFlow`, `capitalExpenditure` (signed as filed, so normally negative) and `freeCashFlow`, which is `None` rather than a guess when capital expenditure is unavailable. Do not substitute `operatingCashFlow + investingCashFlow`: investing cash flow also carries securities and acquisition activity, and can flip the sign.

### Sentiment and metrics

| Method | Description |
|--------|-------------|
| `get_stock_sentiment(ticker)` | The headline sentiment picture in one call: Score, 30-day regime, mention volume, per-source tone, drivers and narrative |
| `get_metrics(symbol, metric_type="sentiment", start_time=None, end_time=None, max_data_points=None)` | Time series for one metric |
| `get_metrics_distribution(symbol, metric_type="mentions", dimension="source", start_time=None, end_time=None)` | A metric broken down by dimension, for example mentions by source |

Metric types are `mentions`, `sentiment`, `sentisense_score`, `social_dominance` and `creators`. `start_time` and `end_time` are epoch **milliseconds**, unlike the epoch-second timestamps elsewhere in this SDK. Both metric methods accept a knowledge base entity slug as well as a ticker; slugs are case-insensitive and discoverable via `get_stock_entities`.

Sentiment polarity and the SentiSense Score are different readings. Polarity sits in `[-1, 1]`; the Score is sentiment weighted by attention, is unbounded, and is banded at 5, 13 and 23 either side of zero. Two fields in the headline response are in different units on purpose: `mentionShare` is a whole-number percent, rounded per source, so the per-source list sums to about 100 rather than exactly 100 and should not be used to reconstruct counts; `socialDominance` is a fraction, where `0.021` means 2.1%.

### News and documents

| Method | Description |
|--------|-------------|
| `get_documents_by_ticker(ticker, source=None, days=None, hours=None, limit=None)` | News and social posts for a stock |
| `get_documents_by_ticker_range(ticker, start_date, end_date)` | Documents inside a date range |
| `get_documents_by_entity(entity_id)` | Documents for a knowledge base entity |
| `search_documents(query, source=None, days=None, limit=None)` | Natural language search across news and social |
| `get_documents_by_source(source, days=None, hours=None, limit=None, sort=None)` | Latest from one source |
| `get_stories(limit=None, days=None, offset=None, filter_hours=None)` | AI-curated news story clusters |
| `get_stories_by_ticker(ticker, limit=None)` | Story clusters for one stock |
| `get_market_summary()` | The AI-generated market summary |

Sources are `news`, `reddit`, `x`, `substack` and `youtube`. Documents carry derived analytics (sentiment, entities, reliability) plus safe metadata such as the URL, source and timestamps.

On a story, `tickers` holds bare symbols and `displayTickers` holds the formatted ones, so pick the field that matches what you are doing rather than reformatting either.

### Insights

| Method | Description |
|--------|-------------|
| `get_stock_insights(ticker, urgency=None, insight_type=None)` | Generated signals for one stock |
| `get_stock_insights_range(ticker, start_date, end_date)` | The same, bounded by an inclusive date range |
| `get_market_insights()` | Market-level signals |
| `get_latest_insights(limit=50, urgency=None)` | Newest signals across the tracked universe. Free keys receive the top 5 |
| `get_user_insights(limit=20, category=None)` | Signals biased toward the authenticated key's watchlist and portfolio |
| `get_insight_types(ticker)` | The insight type strings available for a stock |

### Insider trading (Form 4)

| Method | Description |
|--------|-------------|
| `get_insider_activity(lookback_days=90)` | Market-wide buying and selling, aggregated by ticker |
| `get_insider_trades(ticker, lookback_days=90)` | Individual filed transactions for one stock |
| `get_insider_cluster_buys(lookback_days=90)` | Stocks where three or more distinct insiders bought recently |

Each trade row carries both the raw SEC `transactionCode` and a simplified `transactionType`. Only codes `P` and `S` are open-market trades. Awards, gifts, exercises and code `F`, which is shares withheld by the issuer to cover taxes at vest, are corporate mechanics rather than a decision to trade, and code `F` arrives typed as `SELL`. So filtering on `transactionType` alone overstates selling: read `transactionCode` when you tally discretionary buying or selling. The market-wide activity endpoint already excludes code `F` from its sells server-side.

### Congressional trading

| Method | Description |
|--------|-------------|
| `get_politician_activity(lookback_days=90, limit=None, offset=None)` | Market-wide STOCK Act disclosures |
| `get_politician_filings(ticker, lookback_days=90)` | Disclosed trades in one stock |
| `get_politician_members()` | Tracked members currently in office, with trading summary statistics |
| `get_politician_member(slug, limit=None, offset=None)` | One member's profile, recent trades and top tickers |
| `get_politician_directory(q=None, limit=50, offset=0)` | Discover slugs, including members who have left Congress |

**Paging.** A 90-day window is routinely well over a thousand disclosures, and the activity feed answers with the first page only, with nothing in the payload to say it stopped. Read `.total_count` for the real size on every tier and walk it with `limit` and `offset`; omitting both sends exactly the unpaged request earlier releases sent.

```python
first = client.get_politician_activity(lookback_days=365, limit=500)
print(f"{len(first)} of {first.total_count} disclosures")

more = client.get_politician_activity(lookback_days=365, limit=500, offset=500)
for trade in more:
    print(trade.politicianName, trade.ticker, trade.transactionType)
```

`recentTrades` on a single member is a page too. Most members have a few dozen disclosures and arrive complete in one call, but a handful have thousands. The profile and top-tickers blocks always describe the whole history whatever page you asked for, so `profile.totalTrades` does not shrink with a small `limit`.

The directory is the only one of these that is not tier-gated, and the only one that lists former members, who carry `former` and `servedUntil`. The members roster lists who currently holds office, so a former member is otherwise reachable only if you already know the slug.

### Institutional flows (13F)

| Method | Description |
|--------|-------------|
| `get_institutional_quarters()` | Available 13F reporting quarters |
| `get_institutional_flows(report_date=None, limit=50)` | Fund flows for a quarter, split into inflows and outflows. Omit the date for the latest |
| `get_stock_holders(ticker, report_date, limit=None, offset=None, sort_by=None, sort_dir=None)` | Institutional holders of one stock |
| `get_activist_positions(report_date)` | Activist investor positions for a quarter |
| `get_institution_detail(slug_or_cik)` | One filer's profile, summary stats and current-quarter holdings |
| `list_institutions(category=None, min_aum_usd=None, limit=50, offset=0)` | Discover filers, AUM-ranked, rolled up by parent |

**Paging the holder list.** A widely held ticker returns thousands of rows: a megacap quarter is roughly 6,000 holders and 1.5 MB on the wire. Pass `limit` unless you really want the whole list. Omitting every paging argument sends the original unbounded request, so existing code keeps working.

| Argument | Values |
|----------|--------|
| `limit` | Maximum rows to return. Must be >= 1; values above 1000 are capped server-side. Omit for the full list. |
| `offset` | Row offset to start from, used with `limit`. Server default is 0. |
| `sort_by` | `"shares"` (server default), `"valueUsd"`, or `"sharesChangePct"`. |
| `sort_dir` | `"desc"` (server default) or `"asc"`. |

```python
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

Paged responses carry `returnedCount` and `offset` next to the holder rows, so you can walk the list without re-counting it yourself. Institutions are rolled up by parent filer, so a multi-filer manager appears once with combined AUM.

### Analyst ratings

The price target cone (mean, high, low, upside percent) and the consensus are free for everyone, with full data over the API. Upgrade and downgrade feeds and forward EPS estimates are limited on free and unlimited on PRO.

| Method | Description |
|--------|-------------|
| `get_analyst_consensus(ticker)` | Price target band, analyst count, upside percent. Free for everyone, full data |
| `get_analyst_actions(ticker, lookback_days=90)` | Recent upgrades and downgrades. Free: the 3 most recent |
| `get_analyst_estimates(ticker)` | Forward EPS estimates and surprise history. Free: 1 quarter |
| `get_analyst_market_activity(lookback_days=30)` | Market-wide analyst actions across all covered tickers (PRO) |

### Earnings

The earnings analysis report is the assembled version of a quarter: one object per fiscal period carrying the editorial headline, the KPI cards with year-over-year deltas, the guidance language as management phrased it, and a summary of the earnings call. Pair it with the recent-reporters feed to drive a post-earnings sweep.

| Method | Description |
|--------|-------------|
| `get_earnings_calendar(ticker=None, week=None, date_from=None, date_to=None)` | Scheduled dates and consensus EPS. Free: the current week. PRO: the full forward window |
| `get_earnings_summaries(ticker, limit=None)` | Per-quarter analysis, newest first. Free: the latest quarter, shaped. PRO: every hydrated quarter in full |
| `get_recent_earnings(days=None, limit=None)` | Which covered companies reported in a recent window. Full window on every key |

```python
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

A ticker with no stored quarter answers with an empty list rather than a 404. A quarter can gain its call summary on a later read, so branch on `hasTranscript` and compare `transcriptGeneratedAt` against `generatedAt` rather than assuming a fixed lag. The calendar is the forward-looking half of this family and the recent-reporters feed the backward-looking one; the window there is bounded by report date, so a quarter reported inside it appears even when its call summary lands later.

### Company KPIs (PRO)

| Method | Description |
|--------|-------------|
| `get_company_kpis(ticker)` | Product metrics and segment revenue as time series. Free keys receive metadata only |
| `list_kpi_coverage()` | Every ticker with curated KPI coverage (free, no quota cost) |
| `get_kpi_types(ticker)` | The KPI metadata tuples for a ticker, without paying for the full series |

### ETFs (beta)

Composition data is public. The holdings-weighted aggregate views follow the same preview pattern as analyst and insider data: they synthesize a fund-level view from each constituent's per-stock data, weighted by allocation. Every aggregate response carries a `coverage` block so you can see how much of the fund's weight the underlying data actually covered.

| Method | Description |
|--------|-------------|
| `list_etfs()` | Every ETF tracked: ticker, fund name, issuer, tracked index, asset class |
| `get_etf_holdings(ticker)` | Full composition with per-holding weights and freshness metadata |
| `get_etf_analyst_aggregate(ticker)` | Holdings-weighted analyst consensus, with per-holding contributions in `topContributors` |
| `get_etf_insider_aggregate(ticker, lookback_days=30)` | Holdings-weighted Form 4 net flow over a trailing window, clamped to 90 days |
| `get_etf_sentiment_aggregate(ticker)` | Two Score readings side by side: constituent-weighted and direct |

### Screener

Filter the tracked universe on the SentiSense Score, attention, analyst consensus, technicals and price in one query. Screening on analyst ratings alone is something a dozen free tools do; screening on analyst ratings *where the Score disagrees* is not.

| Method | Description |
|--------|-------------|
| `get_screener_fields()` | Every filterable field, with units, operators and descriptions, for both universes |
| `list_screens()` | The curated screens shipped in the product, each with a runnable plan |
| `run_screen(plan, tickers=None, limit=None)` | Run a screen against the stock universe |
| `run_etf_screen(plan, tickers=None, limit=None)` | Run a screen against the ETF universe |

```python
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

On the ETF side, `CONSTITUENTS_WEIGHTED_SENTISENSE` is the holdings-weighted Score across what the fund owns and is usually the one you want; `DIRECT_SENTISENSE` is the Score from chatter about the fund ticker itself. `WEIGHT_COVERED_PCT` tells you how much of the fund's weight had constituent data behind the weighted number.

Screens read a snapshot that refreshes every 20 minutes, so this is not a quote feed. Use `get_stock_quote` for current quotes.

### Market mood, indexes and trackers

| Method | Description |
|--------|-------------|
| `get_market_mood(days=180)` | The Market Mood composite: latest score, daily history, per-signal breakdown, per-sector summaries |
| `list_indexes()` | Every published index, with the scale it lives on and its access tier |
| `get_index(index_id)` | The latest reading for one index |
| `get_index_history(index_id, days=180)` | An index's historical scalar series, for charting |
| `list_trackers()` | Every publicly visible tracker, with a `viewType` renderer hint |
| `get_tracker(tracker_id)` | The standardized snapshot envelope for one tracker |

Iterate `list_indexes` rather than hardcoding ids. Two archetypes share one envelope: a basket index populates `constituents`, `basketSize`, `coverage` and `totalMentions`, while a composite index such as Market Mood returns `None` for all four by construction, because it is built from signals rather than entities. Check for `None` before iterating constituents. Market Mood's phase band, weekly change and sector map live on the mood method, and both report the same headline number.

History point spacing follows the index rather than the calendar, and thin or low-coverage buckets are withheld, so a series can be shorter than the days you asked for and can contain gaps. Plot against each point's own `date`.

For trackers, dispatch on `data.viewType` to pick a renderer: table rows arrive in `rows`, choropleth regions in `geo`.

### Knowledge base

| Method | Description |
|--------|-------------|
| `get_popular_kb_entities()` | The most-tracked entities, useful for search suggestions |

## Error Handling

```python
from sentisense import SentiSenseClient, AuthenticationError, RateLimitError

client = SentiSenseClient("your-api-key")

try:
    price = client.get_stock_price("AAPL")
except AuthenticationError:
    print("Invalid or missing API key")
except RateLimitError as exc:
    print("Rate limited, retry after", exc.retry_after)
```

| Exception | HTTP Status | Description |
|-----------|-------------|-------------|
| `AuthenticationError` | 401, 403 | Invalid or missing API key, or insufficient tier |
| `NotFoundError` | 404 | Resource not found |
| `RateLimitError` | 429 | Rate limit exceeded. Carries `.retry_after` when the server sent one |
| `DeepHistoryUnavailable` | 202 | Deep chart history (`10Y`, `MAX`) is still being assembled; retry shortly |
| `APIError` | Other 4xx/5xx | General API error |

All exceptions inherit from `SentiSenseError` and carry `.status_code`, `.message` and `.response`.

The client retries 429 and 5xx responses on your behalf up to `max_retries`, so an exception here means the retries were exhausted or the status was not retryable. Deep chart ranges are retried separately: they answer `202` while a cold stock's history is assembled, and the SDK never substitutes a shorter range, so a successful call always carries the timeframe you asked for.

## Not yet in the Python SDK

A few low-traffic and discovery-convenience endpoints have no wrapper method yet. Call them
directly over HTTP if you need them: `/api/v1/stocks/images`, `/api/v1/stocks/descriptions`,
`/api/v1/stocks/popular`, `/api/v1/documents/stories/{clusterId}` (single-story detail), and
`/api/v1/stocks/{ticker}/metrics/{metricType}/breakdown`.

## Links

- Get a free API key: [app.sentisense.ai/get-api-key](https://app.sentisense.ai/get-api-key)
- API documentation: [sentisense.ai/docs/api](https://sentisense.ai/docs/api/)
- Changelog: [CHANGELOG.md](./CHANGELOG.md)

SentiSense provides research data for informational and educational purposes, not investment advice.

## License

MIT - see [LICENSE](LICENSE) for details.
