# SentiSense Python SDK

[![PyPI version](https://img.shields.io/pypi/v/sentisense.svg)](https://pypi.org/project/sentisense/)
[![Python versions](https://img.shields.io/pypi/pyversions/sentisense.svg)](https://pypi.org/project/sentisense/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

The official Python client for the [SentiSense](https://sentisense.ai) API. One client gets you prices and fundamentals, news and social sentiment, the SentiSense Score and Rating, insider and congressional trades, 13F holdings, analyst ratings, earnings, options positioning, ETFs and a screener that mixes all of them.

The client is one flat class with typed results. It retries rate limits and depends only on `requests` (Python 3.8+).

## Contents

- [Install](#install)
- [Quick Start](#quick-start)
- [Authentication and Configuration](#authentication-and-configuration)
- [Reading responses](#reading-responses)
- [What you can call](#what-you-can-call)
- [Error Handling](#error-handling)

## Install

```bash
pip install sentisense
```

You need an API key. The free one at [app.sentisense.ai/get-api-key](https://app.sentisense.ai/get-api-key) works with every endpoint. If you have Node, `npx sentisense init` gets you a temporary key without signing up.

## Quick Start

```python
from sentisense import SentiSenseClient

client = SentiSenseClient()   # reads SENTISENSE_API_KEY from the environment

# Which stocks are covered, with names
tickers = client.get_all_stocks()              # ["A", "AAL", "AAPL", ...]
detailed = client.get_all_stocks_detailed()
print(len(tickers), "stocks;", detailed[0].ticker, detailed[0].simpleName)

# A quick read on one stock
price = client.get_stock_price("NVDA")
print(price.currentPrice, price.changePercent)

score = client.get_metrics("NVDA", metric_type="sentisense_score")
print("SentiSense Score:", score[-1]["value"])

for story in client.get_stories_by_ticker("NVDA", limit=3):
    print(story.cluster.title)

for trade in client.get_insider_trades("NVDA")[:5]:
    print(trade.insiderName, trade.transactionCode, trade.sharesTransacted)
```

## Authentication and Configuration

Pass the key as the first argument, or leave it out and the client reads `SENTISENSE_API_KEY`. Keep it in the environment rather than in your code, so it never lands in git.

```python
client = SentiSenseClient(timeout=30.0, max_retries=3)
```

| Argument | Default | What it does |
|----------|---------|--------------|
| `api_key` | `SENTISENSE_API_KEY` | Your key, sent as the `X-SentiSense-API-Key` header |
| `base_url` | `https://app.sentisense.ai` | Change it only to point at another host |
| `timeout` | `30.0` | Seconds per request |
| `max_retries` | `3` | Retries for the per-minute 429 and server errors. Set `0` to handle them yourself |

## Reading responses

Most methods return a typed object or a list of them. Every object also works like a dict, so `price.currentPrice` and `price["currentPrice"]` are the same. A field the API sends that the object does not declare yet is still there: read it with `price.get("name")`, and `price.extra_fields` lists them.

Endpoints with a free preview return a `PreviewResult`. You read it exactly like the full data, and it tells you whether you got a preview:

```python
trades = client.get_insider_trades("NVDA")
if trades.is_preview:
    print(f"preview: {len(trades)} of {trades.total_count} trades")
    print(trades.upgrade["message"])
```

`trades.sample_company` is `True` when a free key got the full data because the ticker is a sample company.

Document searches return a `DocumentSearchResponse` with the rows in `.documents`. How previews, paging, retries and errors work across both SDKs is on one page: [Using the Python and Node SDKs](https://sentisense.ai/docs/support/using-the-python-and-node-sdks/).

## What you can call

Each section lists the methods and links to the API docs page that explains every field.

### Stocks

| Method | Description |
|--------|-------------|
| `get_stock_price(ticker)` | Latest price, delayed 15 minutes |
| `get_stock_prices(tickers)` | Latest prices for several stocks in one call |
| `get_stock_quote(ticker)` | Day range, 52-week range, market cap, P/E, EPS, dividend yield |
| `get_stock_profile(ticker)` | Company profile |
| `get_stock_entities(ticker)` | People, products and organizations linked to a stock |
| `get_stock_graph(ticker, depth=1, cap=75)` | The company's knowledge graph: people, products and peers |
| `get_similar_stocks(ticker, limit=5)` | Peers with their prices |
| `get_stock_etfs(ticker, limit=None)` | The ETFs that hold a stock, heaviest weight first |
| `get_stock_ai_summary(ticker, depth="basic")` | Our research report on the stock. `depth="deep"` is the full report, capped monthly on free keys |
| `get_stock_chart(ticker, timeframe="1M")` | Price bars, oldest first |
| `get_all_stocks()` | Every ticker we cover |
| `get_all_stocks_detailed()` | The same, with names and entity ids |
| `get_market_status()` | Whether the market is open |

For a fund, use `get_etf_quote`. `get_stock_quote` accepts a fund ticker but leaves out AUM, NAV and expense ratio. Only the `10Y` and `MAX` charts are dividend-adjusted, so don't compare their closes with a `1Y` chart. [Stocks API docs](https://sentisense.ai/docs/api/stocks/)

### Fundamentals

| Method | Description |
|--------|-------------|
| `get_fundamentals(ticker, timeframe="quarterly")` | Income statement, balance sheet and cash flow, as filed |
| `get_current_fundamentals(ticker)` | The latest snapshot |
| `get_fundamentals_periods(ticker)` | The reporting periods we hold |
| `get_fundamentals_history(ticker, timeframe=None, limit=None)` | Up to 40 quarters or 20 years of statements, newest first, with each period's SEC sources when we hold them |
| `get_historical_revenue(ticker)` | Revenue over time |
| `get_short_interest(ticker)` | Short interest by settlement date |
| `get_float(ticker)` | Shares available to trade |
| `get_short_volume(ticker)` | Daily short-sale volume |

Figures are in the company's own currency (`reportedCurrency`), never converted. [Fundamentals in the Stocks API docs](https://sentisense.ai/docs/api/stocks/)

### Sentiment and metrics

| Method | Description |
|--------|-------------|
| `get_stock_sentiment(ticker)` | The headline picture in one call: Score, mentions, tone by source, what's driving it |
| `get_metrics(symbol, metric_type="sentiment", start_time=None, end_time=None, max_data_points=None)` | One metric over time |
| `get_metrics_distribution(symbol, metric_type="mentions", dimension="source", start_time=None, end_time=None)` | One metric split by source |

Metric types are `mentions`, `sentiment`, `sentisense_score`, `sentisense_rating`, `social_dominance`, `creators`, `app_review_count`, `app_rating`, `app_all_ratings_count` and `app_all_ratings_avg`.

Sentiment runs from -1 to 1. The SentiSense Score is sentiment weighted by attention and has no fixed range. `start_time` and `end_time` are epoch milliseconds. [Metrics API docs](https://sentisense.ai/docs/api/metrics/)

### SentiSense Rating

| Method | Description |
|--------|-------------|
| `get_rating(ticker)` | Today's score, letter grade and percentile, with the seven dimensions behind it |

```python
rating = client.get_rating("AAPL")
if rating.rated:
    print(rating.letter, rating.score, "percentile", rating.percentile)
else:
    print("no grade today:", rating.reason)
```

Check `rated` first, because an unrated stock comes back as a normal response. Each response carries a `disclaimer` to show next to the grade. [Rating API docs](https://sentisense.ai/docs/api/sentisense-rating/)

### News and documents

| Method | Description |
|--------|-------------|
| `get_documents_by_ticker(ticker, source=None, days=None, hours=None, limit=None)` | News and social posts about a stock |
| `get_documents_by_ticker_range(ticker, start_date, end_date)` | The same, for a date range |
| `get_documents_by_entity(entity_id)` | Posts about a person, product or company |
| `search_documents(query, source=None, days=None, limit=None)` | Search news and social in plain language |
| `get_documents_by_source(source, days=None, hours=None, limit=None, sort=None)` | The latest from one source |
| `get_stories(limit=None, days=None, offset=None, filter_hours=None)` | Today's stories, each a cluster of related coverage |
| `search_stories(query, days=7, limit=20)` | Search stories, newest first |
| `get_story_detail(story_id)` | One story in full, with the bull and bear views |
| `get_stories_by_ticker(ticker, limit=None)` | Stories about one stock |
| `get_market_summary()` | Our written market summary |

Sources are `news`, `reddit`, `x`, `substack` and `youtube`. Documents carry sentiment, entities and a link, not the article text. [Documents API docs](https://sentisense.ai/docs/api/documents/)

### Insights

| Method | Description |
|--------|-------------|
| `get_stock_insights(ticker, urgency=None, insight_type=None)` | Signals for one stock |
| `get_stock_insights_range(ticker, start_date, end_date)` | The same, for a date range |
| `get_market_insights()` | Market-wide signals |
| `get_latest_insights(limit=50, urgency=None)` | The newest signals across every stock. Free keys get the top 5 |
| `get_user_insights(limit=20, category=None)` | Signals for your watchlist and portfolio |
| `get_insight_types(ticker)` | Which signal types exist for a stock |

[Insights API docs](https://sentisense.ai/docs/api/insights/)

### Insider trading (Form 4)

| Method | Description |
|--------|-------------|
| `get_insider_activity(lookback_days=90)` | Buying and selling across the market, by ticker |
| `get_insider_trades(ticker, lookback_days=90)` | Each filed trade in one stock |
| `get_insider_cluster_buys(lookback_days=90)` | Stocks where three or more insiders bought recently |

Count real buying and selling by `transactionCode` (`P` and `S` are open-market trades). `transactionType` also labels shares withheld for taxes, code `F`, as `SELL`. [Insider API docs](https://sentisense.ai/docs/api/insider-trading/)

### Options

| Method | Description |
|--------|-------------|
| `get_options_overview()` | Where options activity is unusual today, stocks and ETFs ranked separately |
| `get_stock_options_summary(ticker)` | One stock's options picture: volatility, put/call, walls, unusual contracts |
| `get_stock_options_history(ticker, window="1y")` | The same readings as a daily series |
| `get_stock_options_intraday_history(ticker, session=None)` | Every 15-minute reading from one session (PRO) |

Apart from the intraday history, these are end-of-day readings, each measured against the stock's own past year. For an uncovered ticker the summary's `data` is `None`. [Options API docs](https://sentisense.ai/docs/api/options/)

### Congressional trading

| Method | Description |
|--------|-------------|
| `get_politician_activity(lookback_days=90, limit=None, offset=None)` | Recent trades disclosed by members of Congress |
| `get_politician_filings(ticker, lookback_days=90)` | Disclosed trades in one stock |
| `get_politician_members()` | Members in office, with trading stats |
| `get_politician_member(slug, limit=None, offset=None)` | One member's profile and trades |
| `get_politician_directory(q=None, limit=50, offset=0)` | Find a member's slug, including former members |

The activity feed comes back a page at a time, so walk it with `limit` and `offset` until you reach `total_count`:

```python
page = client.get_politician_activity(lookback_days=365, limit=500)
print(f"{len(page)} of {page.total_count} disclosures")
```

[Politicians API docs](https://sentisense.ai/docs/api/politicians/)

### Institutional flows (13F)

| Method | Description |
|--------|-------------|
| `get_institutional_quarters()` | The 13F quarters we hold, newest first |
| `get_institutional_flows(report_date=None, limit=50)` | The quarter's biggest inflows and outflows |
| `get_stock_holders(ticker, report_date=None, limit=None, offset=None, sort_by=None, sort_dir=None)` | Who holds a stock |
| `get_stock_holders_history(ticker, quarters=None)` | A stock's institutional ownership, quarter by quarter |
| `get_activist_positions(report_date)` | Activist positions for a quarter |
| `get_institution_detail(slug_or_cik, limit=None, offset=None, sort_by=None, sort_dir=None, change_type=None, q=None, min_weight=None)` | One fund's holdings and what changed since its last filing |
| `get_institution_history(slug_or_cik, quarters=None, tickers=None)` | One fund's book, filing by filing |
| `list_institutions(category=None, min_aum_usd=None, limit=50, offset=0)` | Find funds, largest first |

The newest quarter is often incomplete, so pick one by its `pending` flag rather than taking the first. A widely held stock has thousands of holders, so pass `limit` to `get_stock_holders`. On `get_stock_holders` and `get_institution_detail`, the sort and filter arguments are ignored without `limit`.

```python
filed = [q for q in client.get_institutional_quarters() if not q.get("pending")]
top = client.get_stock_holders("AAPL", filed[0]["reportDate"], limit=10, sort_by="valueUsd")
for holder in top.holders:
    print(holder["filerName"], holder["valueUsd"])
```

[13F API docs](https://sentisense.ai/docs/api/institutional-flows/)

### Analyst ratings

| Method | Description |
|--------|-------------|
| `get_analyst_consensus(ticker)` | Price target range, analyst count and upside. Free keys get the price target range |
| `get_analyst_consensus_history(ticker, from_date=None, to_date=None, limit=None)` | The consensus day by day |
| `get_analyst_called_it(ticker, limit=None)` | Which analysts called the stock's big moves |
| `get_analyst_actions(ticker, lookback_days=90)` | Upgrades and downgrades, with each firm's price target |
| `get_analyst_estimates(ticker)` | EPS estimates and past surprises |
| `get_analyst_market_activity(lookback_days=30)` | Analyst actions across every stock |
| `get_analyst_coverage(ticker, lookback_days=None)` | Who covers a stock and what they said last |
| `get_analyst_profile(slug)` | One analyst and the stocks they cover |
| `get_analyst_calls(slug, limit=None, offset=None)` | One analyst's price target notes, newest first |

Action rows are plain dicts. `priceTarget` is `None` when the firm gave none. [Analyst API docs](https://sentisense.ai/docs/api/analyst-ratings/)

### Earnings

| Method | Description |
|--------|-------------|
| `get_earnings_calendar(ticker=None, week=None, date_from=None, date_to=None)` | Upcoming report dates and EPS estimates |
| `get_earnings_summaries(ticker, limit=None)` | Each quarter written up: headline, KPIs, guidance, call summary |
| `get_recent_earnings(days=None, limit=None)` | Who reported recently |
| `get_earnings_reactions(ticker)` | How the stock moved after each of its last reports |
| `get_earnings_statistics(window=None)` | Beat rates and reactions across the market |
| `get_ranked_earnings(reported_days=None, reported_limit=None, upcoming_days=None, upcoming_limit=None)` | The reports that mattered most, past and upcoming |

```python
for quarter in client.get_earnings_summaries("AAPL", limit=1):
    print(quarter.fiscalPeriod, quarter.headline)
```

[Earnings API docs](https://sentisense.ai/docs/api/earnings/)

### Company KPIs (PRO)

| Method | Description |
|--------|-------------|
| `get_company_kpis(ticker)` | Product and segment metrics over time, like iPhone revenue or Tesla deliveries |
| `list_kpi_coverage()` | Which companies have KPIs (free, no quota cost) |
| `get_kpi_types(ticker)` | Which KPIs a company has |

Free keys get the full series for the [sample companies](https://sentisense.ai/docs/api/#full-sample-responses-with-a-free-key), such as TSLA, and a preview for the rest.

### ETFs (beta)

| Method | Description |
|--------|-------------|
| `list_etfs()` | Every ETF we track |
| `get_etf_quote(ticker)` | A fund's quote with AUM, expense ratio and NAV |
| `get_etf_holdings(ticker)` | What the fund holds, with weights |
| `get_etf_analyst_aggregate(ticker)` | Analyst consensus across the holdings, by weight |
| `get_etf_insider_aggregate(ticker, lookback_days=30)` | Insider buying and selling across the holdings |
| `get_etf_sentiment_aggregate(ticker)` | The fund's Score, from its holdings and from talk about the fund itself |

[ETF API docs](https://sentisense.ai/docs/api/etfs/)

### Screener

| Method | Description |
|--------|-------------|
| `get_screener_fields()` | Every field you can filter on |
| `list_screens()` | Our ready-made screens |
| `run_screen(plan, tickers=None, limit=None)` | Run a screen over stocks |
| `run_etf_screen(plan, tickers=None, limit=None)` | Run a screen over ETFs |

```python
# High 7-day Score, few analyst buy ratings
res = client.run_screen(
    {
        "filters": [
            {"fieldName": "SENTI_SCORE_7D", "op": "GTE", "value": 13},
            {"fieldName": "ANALYST_BUY_RATIO_PCT", "op": "LTE", "value": 30},
        ],
        "sort": {"fieldName": "SENTI_SCORE_7D", "dir": "DESC"},
    },
    limit=25,
)
for row in res.results:
    print(row.ticker, row.sentiSenseScore7D, row.analystBuyRatioPct)
```

`ANALYST_RATING_MEAN` runs backwards (1 is strong buy), so prefer `ANALYST_BUY_RATIO_PCT`. [Screener API docs](https://sentisense.ai/docs/api/screener/)

### Market mood, indexes and trackers

| Method | Description |
|--------|-------------|
| `get_market_mood(days=180)` | Market Mood, from fear to greed, with its history |
| `list_indexes()` | Our indexes |
| `get_index(index_id)` | One index today |
| `get_index_history(index_id, days=180)` | One index over time |
| `list_trackers()` | Our trackers |
| `get_tracker(tracker_id, filter=None)` | One tracker's data, optionally filtered |

Tracker rows keep any column we don't type yet, so `row.get("marketCap")` works. [Trackers API docs](https://sentisense.ai/docs/api/trackers/)

### Knowledge base

| Method | Description |
|--------|-------------|
| `get_popular_kb_entities()` | The most-followed people, products and companies |

## Error Handling

```python
from sentisense import SentiSenseClient, NotFoundError, RateLimitError

try:
    price = client.get_stock_price("AAPL")
except NotFoundError as exc:
    print("Not covered:", exc.code)
except RateLimitError as exc:
    print(exc.message)
```

| Exception | HTTP Status | When |
|-----------|-------------|------|
| `AuthenticationError` | 401, 403 | The key is missing or wrong |
| `NotFoundError` | 404 | We don't track that symbol, or hold nothing of that kind for it |
| `RateLimitError` | 429 | The per-minute limit (`.retry_after`) or the monthly allowance (`.code == "quota_exceeded"`) |
| `DeepHistoryUnavailable` | 202 | A `10Y` or `MAX` chart is still being built. Try again shortly |
| `TemporarilyUnavailable` | 503 | The server asked for a longer wait than the client allows |
| `APIError` | other | Anything else |

All of them inherit from `SentiSenseError` and carry `.status_code`, `.message`, `.code` and `.response`. The client already retried what it could before raising.

## Not yet in the Python SDK

A few endpoints have no method yet. Call them over HTTP if you need them: `/api/v1/stocks/images`,
`/api/v1/stocks/descriptions`, `/api/v1/stocks/popular`, `/api/v1/kb/entities/search` and
`/api/v1/stocks/{ticker}/metrics/{metricType}/breakdown`.

## Links

- API docs: [sentisense.ai/docs/api](https://sentisense.ai/docs/api/)
- Help with keys, limits and previews: [sentisense.ai/docs/support](https://sentisense.ai/docs/support/)
- Changelog: [CHANGELOG.md](./CHANGELOG.md)

SentiSense provides research data for informational and educational purposes, not investment advice.

## License

MIT. See [LICENSE](LICENSE).
