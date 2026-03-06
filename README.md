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

# Get sentiment for a stock
sentiment = client.get_sentiment("NVDA")
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

### Sentiment & Mentions

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

## License

MIT - see [LICENSE](LICENSE) for details.
