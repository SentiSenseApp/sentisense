# Changelog

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
  Use `get_popular_kb_entities()` / `get_all_kb_entities()`.

## 0.28.0

- `get_institutional_flows`: `report_date` is now optional (omit it for the latest quarter);
  added quarter coverage fields.
- `get_market_summary`: `total_mentions` / `top_active_stocks` documented as no longer populated.
