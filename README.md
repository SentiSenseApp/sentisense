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

# Get sentiment time series
sentiment = client.get_metrics("NVDA", metric_type="sentiment")

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
| `get_stock_chart(ticker, timeframe="1M")` | OHLCV chart data |
| `get_all_stocks()` | List of available tickers |
| `get_all_stocks_detailed()` | Tickers with company names and entity IDs |
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
| `get_kb_entity(entity_id)` | Entity detail with metrics and relationships |
| `get_all_kb_entities()` | All tracked KB entities |

### News & Documents

| Method | Description |
|--------|-------------|
| `get_documents_by_ticker(ticker, source?, days?, hours?, limit?)` | News and social posts for a stock |
| `get_documents_by_ticker_range(ticker, start_date, end_date)` | Documents within a date range |
| `get_documents_by_entity(entity_id)` | Documents for a KB entity |
| `search_documents(query, source?, days?, limit?)` | Natural language search across news and social |
| `get_documents_by_source(source, days?, hours?, limit?)` | Latest from a source ("news", "reddit", "x", "substack") |
| `get_stories(limit?, days?, expanded?)` | AI-curated news story clusters |
| `get_story(cluster_id)` | Single story with all source documents |
| `get_stories_by_ticker(ticker, limit?)` | Stories for a specific stock |

### Metrics (v2)

| Method | Description |
|--------|-------------|
| `get_metrics(symbol, metric_type="mentions", start_time?, end_time?, max_data_points?)` | Time series for a metric (mentions, sentiment, sentisense_score, social_dominance, creators) |
| `get_metrics_distribution(symbol, metric_type="mentions", dimension="source", start_time?, end_time?)` | Metric distribution by dimension (e.g. mentions by source) |

> **Note:** `start_time` and `end_time` are epoch milliseconds.

### Sentiment & Mentions (deprecated)

The following methods hit the v1 entity-metrics endpoints which return empty data. Use the v2 metrics methods above instead.

| Method | Description |
|--------|-------------|
| `get_mentions(symbol, source?, start_date?, end_date?)` | Mention data across news and social |
| `get_mention_count(symbol, source?, start_date?, end_date?)` | Total mention count |
| `get_mention_count_by_source(symbol, start_date?, end_date?)` | Mentions broken down by source |
| `get_sentiment(symbol, start_date?, end_date?)` | Sentiment data for a stock |
| `get_sentiment_by_source(symbol, date?)` | Sentiment broken down by source |
| `get_average_sentiment(symbol, start_date?, end_date?)` | Average sentiment score |

### Institutional Flows (13F)

| Method | Description |
|--------|-------------|
| `get_institutional_quarters()` | Available 13F reporting quarters |
| `get_institutional_flows(report_date, limit=50)` | Fund flows for a quarter |
| `get_stock_holders(ticker, report_date)` | Institutional holders for a stock |
| `get_activist_positions(report_date)` | Activist investor positions |

### Analyst Ratings

The **price target cone** (mean, high, low, upside %) and consensus are **free for everyone, full data via API** — we give it away. Upgrade/downgrade feeds and forward EPS estimates are limited on free, unlimited on PRO.

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

### ETFs (beta)

Composition data is public; the holdings-weighted aggregate views follow the same PRO-with-preview pattern as Analyst/Insider. Aggregates synthesize fund-level views from each constituent's per-stock data (analyst coverage, insider trades, sentiment), weighted by allocation. Every aggregate response carries a `coverage` block so you see exactly how much of the fund's AUM the underlying data covered.

| Method | Description |
|--------|-------------|
| `list_etfs()` | Every ETF tracked by SentiSense. Returns ticker, fund name, issuer, tracked index, asset class. |
| `get_etf_holdings(ticker)` | Full composition: per-holding weights and freshness metadata. |
| `get_etf_analyst_aggregate(ticker)` | Holdings-weighted analyst consensus (weighted upside, distribution). Free: headline + coverage. PRO: + `topContributors`. |
| `get_etf_insider_aggregate(ticker, lookback_days=30)` | Holdings-weighted Form 4 net flow over a configurable window. Free: headline + buy/sell split. PRO: + `topContributors`. |
| `get_etf_sentiment_aggregate(ticker)` | Two SentiSense readings side-by-side: constituent-weighted and direct (mentions of the fund itself). |

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
| `APIError` | Other 4xx/5xx | General API error |

All exceptions inherit from `SentiSenseError` and include `.status_code`, `.message`, and `.response` attributes.

## Not yet in the Python SDK

A few endpoints available in the Node SDK are intentionally not yet exposed here
(low-traffic / discovery-convenience surfaces). Call them directly over HTTP if you
need them: `/api/v1/stocks/images`, `/api/v1/stocks/descriptions`,
`/api/v1/stocks/popular`, `/api/v1/stocks/{ticker}/entities`,
`/api/v1/stocks/{ticker}/ai-summary`, and the metrics breakdown endpoint.

## License

MIT - see [LICENSE](LICENSE) for details.
