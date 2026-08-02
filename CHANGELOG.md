# Changelog

## 0.33.0

### Added

- **`get_stock_sentiment(ticker)`.** One call for a stock's headline sentiment picture: the
  SentiSense Score with its 30-day regime (`sentisenseScore`, `sentisenseScoreAvg30d`,
  `scoreLabel`, `direction`, `trend`, `scoreSparkline`), mention volume and social dominance,
  per-source tone in `bySource`, plus related tickers, story drivers, a narrative and an FAQ.
  Available in full on every API-key tier. Use `get_metrics(..., metric_type="sentiment")`
  instead when you need a time series over a specific window.

### Fixed

- **`Retry-After` is now validated and clamped.** A large value previously blocked the calling
  thread for its full duration, and on the rate-limit path a non-numeric value (the header may
  legally carry an HTTP-date) raised `ValueError` out of the client. Waits are now bounded at 30
  seconds for deep-history retries and 120 seconds for rate limiting, and any non-finite or
  unparseable value falls back to the default wait.

## 0.32.0

### Added

- **`reportedCurrency` on fundamentals responses.** Names the currency the filer reports in
  ("USD", "KRW", "EUR", ...). Statement figures are as reported in that currency and are never
  converted to US dollars; foreign companies listed as ADRs file in their home currency while
  their listed share price is in USD. When the key is absent the currency is unknown, not
  implicitly USD. For non-USD filers the API serves `peRatio` / `psRatio` / `pbRatio` as `None`
  on purpose: a USD price over a home-currency per-share figure is a unit mismatch, so do not
  recompute them client-side.

## 0.30.0

### Breaking (removed)

- `get_all_kb_entities`. The unpaginated full-entity dump endpoint has been retired
  server-side (HTTP 410). Use `get_popular_kb_entities()` for suggestions, or
  `get_stock_entities(ticker)` for the entities related to a ticker.

### Added

- `get_stock_entities(ticker)`: the tracked entities related to a stock (executives,
  products, organizations). Already available in the Node SDK as `stocks.getEntities`.

## 0.29.0

Removed methods whose endpoints no longer work. All were unusable at runtime, so this
breaks only code that was already failing.

### Breaking (removed)

- `get_mentions`, `get_mention_count`, `get_mention_count_by_source`, `get_sentiment`,
  `get_sentiment_by_source`, `get_average_sentiment`. These called the v1
  `/entity-metrics/` endpoints, which the API retired in March 2026 (HTTP 410). Use
  `get_metrics(symbol, metric_type=...)` and `get_metrics_distribution(symbol, metric_type=...)`
  instead.
- `get_kb_entity`. Its endpoint returned 400/404 for every id form, so it never worked.
  Use `get_popular_kb_entities()`. (This entry originally also pointed at
  `get_all_kb_entities`, which was itself removed in 0.30.0.)

## 0.28.0

- `get_institutional_flows`: `report_date` is now optional (omit it for the latest quarter);
  added quarter coverage fields.
- `get_market_summary`: `total_mentions` / `top_active_stocks` documented as no longer populated.
