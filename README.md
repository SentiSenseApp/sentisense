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
