# Changelog

## 0.37.0

### Added

- **`get_earnings_summaries(ticker, limit=None)`.** The per-quarter earnings analysis report:
  one `EarningsQuarter` per fiscal period carrying the editorial headline, the KPI cards
  with year-over-year deltas, the guidance language as management phrased it, and a
  summary of the earnings call. Auto-unwrapped, so iterate the result or read
  `result.data`, and branch on `result.is_preview`: a PRO key receives every hydrated
  quarter in full, a FREE key receives the latest quarter shaped rather than truncated
  (section titles in `summaryTopics` and `transcriptTopics`, `guidanceDirection` in place
  of the guidance language, two KPI cards plus `kpiHighlightCount`). A ticker with no
  stored quarter answers with an empty list rather than a 404, and a quarter can gain its
  call summary on a later read, so branch on `hasTranscript` and compare
  `transcriptGeneratedAt` against `generatedAt` rather than assuming a fixed lag.

- **`get_recent_earnings(days=None, limit=None)`.** The cross-ticker view of who reported
  recently, newest first, as `RecentEarningsEntry` rows. Every key receives the full
  window it asks for. The window is bounded by `reportDate`, so a quarter reported inside
  it appears even when its call summary lands later. This is the backward-looking feed;
  `get_earnings_calendar` remains the forward-looking one.

- New types: `EarningsQuarter`, `EarningsKpiHighlight`, `EarningsSource` and
  `RecentEarningsEntry`, all exported from the package root.

## 0.36.0

### Added

- **`list_indexes()`, `get_index(index_id)` and `get_index_history(index_id, days=180)`.**
  Typed access to the published indexes, with models for the listing, the snapshot, its
  constituents and the history series. A basket index fills `constituents`, `basketSize`,
  `coverage` and `totalMentions`; a composite index returns `None` for all four by
  construction, so check for `None` before iterating.

## 0.35.0

### Added

- **`get_stock_ai_summary(ticker, depth="basic")`.** The curated AI research report was
  reachable from the Node SDK but not from here, so Python callers had to hand-roll the
  request. `depth="basic"` returns the one-paragraph summary; `depth="deep"` returns the
  full report plus `moatRating` and `aiDisruptionRisk`, and consumes one report view per
  call on metered tiers. The response is flat, not a preview envelope, and a ticker with
  no published report answers with `status` of `"NOT_AVAILABLE"` rather than raising, so
  branch on `status` before reading `sections`. Note that `lastUpdated` here is epoch
  milliseconds, unlike the epoch-second timestamps elsewhere in this SDK.

## 0.34.0

### Added

- **`get_politician_activity` can page.** The endpoint reports thousands of trades for a
  wide lookback but answers with the first page only, so the previous signature could
  reach a small fraction of the window with no way to advance. Added keyword-only
  `limit` and `offset`, sent only when supplied; read `result.total_count` to size the
  window first. Omitting both produces exactly the request the previous release sent.

- **`get_stock_holders` gained keyword-only `limit`, `offset`, `sort_by` and
  `sort_dir`.** A megacap quarter is roughly 6,000 holder rows and 1.5 MB, which used to
  arrive in one unbounded response. Paged responses carry `returnedCount` and `offset`
  next to the rows. Omitting every paging argument keeps the original request.

- **`StockQuote.reportedCurrency`.** Names the currency the filer reports in and travels
  with the quote's filing-derived fields (`epsTTM`, `peRatio`). `None` means unknown,
  not USD. Price fields remain in the exchange's listing currency, which for an ADR is
  USD even when the filer reports in something else.

### Fixed

- **`get_stock_chart` declared the wrong return type.** It was annotated
  `Dict[str, Any]` while the endpoint has always answered with a bare list of bars
  (verified across 1D, 1M, 1Y, 5Y, 10Y and MAX). The package ships `py.typed`, so type
  checkers were steering callers into `chart["close"]`, which raises at runtime. Now
  annotated `List[Dict[str, Any]]`. Runtime behaviour is unchanged.

- **The chart adjustment boundary is 10Y, not 5Y.** The docstring said ranges of 5Y and
  longer were split- and dividend-adjusted. Sampled live on two tickers with very
  different payout rates: 5Y weekly closes match the unadjusted daily series exactly,
  while 10Y and MAX carry a dividend discount. Only 10Y and MAX are dividend-adjusted.

- **`mentionShare` does not sum to exactly 100.** The `get_stock_sentiment` docstring
  promised it did. Each source's share is rounded independently, so the list sums to
  about 100; sampled across 7 tickers, 3 summed to 101. Reworded, and callers are told
  not to reconstruct per-source counts from the shares.

- **`get_stock_entities` documented fields the endpoint never sends.** The docstring
  listed `entityId`, `name`, `type`; the wire sends `id`, `displayName`, `type`,
  `relatedStock`, `urlSlug`, plus nullable `title`, `category` and `iconUrl`.

- **README corrections.** Removed `get_story(cluster_id)`, which was listed in the
  method table but has never existed and raised `AttributeError`; its endpoint is now
  named in the "Not yet in the Python SDK" section instead. Corrected the documented
  `get_metrics` default, which is `"sentiment"` and was shown as `"mentions"`. Added
  `DeepHistoryUnavailable` to the exception table, which reads as exhaustive. Dropped
  the stale claim that `/api/v1/stocks/{ticker}/entities` is unavailable, since
  `get_stock_entities` has shipped since 0.30.0.

Documentation claims of this kind are now covered by tests rather than review, so a
README default, an advertised method, or a missing exception row fails the build.

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

There is no 0.31.0 on PyPI. The version was bumped locally and the work went out inside
this release; the entries below were reconstructed after the fact and were missing from
the 0.32.0 release notes.

### Added

- **`DeepHistoryUnavailable`, and automatic retries on deep chart ranges.** `10Y` and
  `MAX` answer `202` the first time a rarely-requested stock is asked for, while its
  history is assembled. `get_stock_chart` now retries that automatically, honouring
  `Retry-After`, and raises `DeepHistoryUnavailable` if the series is still not ready.
  It never substitutes a shorter range, so a successful call always carries the
  timeframe you asked for.

- **`5Y`, `10Y` and `MAX` documented on `get_stock_chart`.** `MAX` returns the full
  available history, up to about 26 years. `ALL` is a legacy alias of `5Y` and is still
  accepted.

- **`reportedCurrency` on fundamentals responses.** Names the currency the filer reports in
  ("USD", "KRW", "EUR", ...). Statement figures are as reported in that currency and are never
  converted to US dollars; foreign companies listed as ADRs file in their home currency while
  their listed share price is in USD. When the key is absent the currency is unknown, not
  implicitly USD. For non-USD filers the API serves `peRatio` / `psRatio` / `pbRatio` as `None`
  on purpose: a USD price over a home-currency per-share figure is a unit mismatch, so do not
  recompute them client-side.

### Documented

- **Cash-flow keys on `get_fundamentals`.** `operatingCashFlow`, `investingCashFlow`,
  `financingCashFlow`, `capitalExpenditure` (signed as filed, so normally negative) and
  `freeCashFlow`, which is `None` rather than a guess when capital expenditure is
  unavailable. Do not substitute `operatingCashFlow + investingCashFlow`: investing cash
  flow also carries securities and acquisition activity and can flip the sign.

- **`get_metrics` and `get_metrics_distribution` accept an entity slug**, not just a
  ticker. Slugs are case-insensitive; discover them via `get_stock_entities()`.

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
