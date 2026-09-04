# Changelog

## 0.47.0

### Added

- **The SentiSense Rating, new to this SDK.** `get_rating(ticker)` returns where a stock
  ranks against the other stocks rated that day: a letter, a percentile, the composite
  behind it, and the six dimensions the composite is blended from. It is a relative
  research signal for informational and educational purposes, not financial, investment or
  trading advice and not a recommendation about any security. Every response carries the
  wording to display alongside a grade in `disclaimer`.
  [Methodology](https://sentisense.ai/methodology/#sentisense-rating).
- Typed models exported from the package root: `StockRating`, `RatingDimension`,
  `RatingSubLeg` and `RatingFlag`.
- `sentisense_rating` is documented as a metric type on `get_metrics()`, which serves the
  daily history of a stock's percentile. It is a time series only: there is no source
  breakdown, so `get_metrics_distribution()` answers with an empty distribution for it.
- `get_analyst_coverage()` now returns `ratingBuckets` next to `firmCount`: how many
  covering firms sit in each rating tier, as `buy`, `hold`, `sell`, `unrated` and `total`.
  Counted over the whole book before the free truncation, so `buy + hold + sell +
  unrated == total` and a free key reads the same numbers as a PRO one. `unrated` is a
  desk with no current rating on record, such as a price-target-only firm. It counts the
  firms in the coverage book, which is a different population from the `strongBuy`
  through `strongSell` survey figures on `get_analyst_consensus()`.

Two shapes to read rather than assume, both gated by tests. **Branch on `rated`.** A rated
stock carries `letter`, `percentile`, `composite`, `ratedCount` and `methodologyVersion`;
an unrated one leaves all five `None` and carries `reason`, `dimensionsPresent` and
`presentDimensions` instead. Not being rated is a normal `200`, not a `404`: ETFs and
tickers outside the swept universe answer that way, and `reason` says which case it is.
And `dimensions` always holds all six rows in a fixed order, including the ones with no
data, which arrive with `present` false and a `None` percentile. Read `present` first and
never substitute zero for a missing percentile: zero is the bottom of the cross-section,
absence is not a position on it.

## 0.46.0

### Added

- **Analyst coverage by name, new to this SDK.** `get_analyst_coverage(ticker)` answers
  "who covers this stock and what did they most recently say", grouped by firm and ordered
  by most recent activity. `get_analyst_profile(slug)` returns one analyst: the firms they
  have published under, the window of notes we hold at each, and their coverage book.
  `get_analyst_calls(slug, limit=None, offset=None)` returns that analyst's price target
  notes, newest first and paged.
- The three surfaces link up: every named analyst on a coverage row carries the `slug` that
  addresses their profile and their calls, so a ticker is one call away from a person's
  full call history. An unknown slug raises `NotFoundError`, which keeps "we hold nothing
  from this analyst" distinguishable from "this analyst does not exist".

Two coverage shapes to read rather than assume. A firm can cover a stock on rating actions
alone, with no price target: that row carries `noteCount` 0, a `None` `latestNote` and a
populated `firmRating`. And a large, publisher-dependent share of notes name no individual
analyst, so a firm can appear with an empty `analysts` list and a non-zero `noteCount`. Read
`attributedNoteCount` and `unattributedNoteCount` off the response rather than hardcoding a
rate. On a FREE key the rows truncate to 5 firms but every response-level count still
describes the whole window.

## 0.45.0

### Added

- `EtfInfo.imageUrl`: the curated landscape card image for a fund, returned by
  `list_etfs()`. It is a wide presentation image rather than a square logo mark, so it
  suits a list row or a profile header. `None` when a fund has no curated image.
- `get_stock_profile()` carries the same `imageUrl` for a tracked ETF ticker. The
  method already returns the raw payload, so this is a documentation change only.

## 0.44.0

### Added

- **Options Intelligence, new to this SDK.** `get_options_overview()` returns the market-wide
  radar, `get_stock_options_summary(ticker)` returns one name's end-of-day dossier, and
  `get_stock_options_history(ticker, window)` returns its daily aggregates as a series over
  `1y`, `2y` or `5y`.
- Typed models for all of it, exported from the package root: `OptionsOverview`,
  `OptionsOverviewRow`, `OptionsSummary`, `OptionsHistory`, `OptionsAggregate`,
  `OptionsContext`, `OptionsOiWalls`, `OptionsWall`, `OptionsUnusualContract`.

Two shapes to know before charting any of it. The radar's `rows` and `etfRows` are
separately-ranked boards with their own aggregates and must not be merged, because every
reading behind a row's score is a percentile of that ticker's own history rather than of the
board. And the two per-ticker methods report no coverage differently: the dossier returns a
`None` payload, the history returns an empty `series`.

## 0.43.0

### Fixed

- **`get_all_stocks_detailed()` now carries the company names it promised.** The API returns
  `simpleName` ("Agilent") and `companyName` ("Agilent Technologies, Inc."), but `StockDetail`
  only declared a `name` field that the API never sends, so every row came back with an empty
  name. `simpleName` and `companyName` are now real fields, and `name` falls back to
  `simpleName` so existing code reads a name instead of `""`.
- **The price methods no longer describe themselves as real-time.** `get_stock_price` and
  `get_stock_prices` said "real-time" while the `StockPrice` model they return said
  "delayed 15 minutes". The delay is the true one, and it is now stated in both places.
  Read `priceAsOf` for the actual age of a reading.
- **The insider transaction fields no longer imply that `transactionType` is enough.**
  Filtering to `BUY`/`SELL` was documented as the way to tally open-market activity, but
  Form 4 code `F`, shares withheld by the issuer to cover taxes at vest, arrives typed as
  `SELL`, so that filter overstates selling. Both fields now say to read the raw
  `transactionCode` and keep only `P` and `S`.
- **The README documented `get_stories(expanded=...)`, which is not an argument.** The
  method takes `limit`, `days`, `offset` and `filter_hours`.
- **The API key link pointed at a retired path.** Keys are issued at
  `app.sentisense.ai/get-api-key`.

### Changed

- **The README was reorganized.** It opens with what the SDK covers, the feature list and
  the key and docs links, then a contents list, then Install, Quick Start, Authentication
  and Configuration, Response Shapes, the API reference grouped by subject, and Error
  Handling. The client's constructor options and the two response wrappers were previously
  undocumented, and roughly half the client's methods were missing from the reference:
  insider trading, congressional trading, insights, earnings calendar, market mood,
  indexes, trackers, quotes, peers, headline sentiment and the market summary are all
  documented now.

### Added

- `StockDetail.brandColor` and `StockDetail.socialDominance` (value, rank, percentile), both
  already present in the response and previously discarded.
- Mechanical gates on the new docs: every `client.x(...)` call inside a README code fence
  must resolve, the Score keeps one spelling across the README and both metrics docstrings,
  and `StockDetail` must keep carrying the company names the README promises. The method
  tables were already gated; the runnable snippets were not.
- Quick Start now opens with the tracked universe (`get_all_stocks()` /
  `get_all_stocks_detailed()`) and shows the SentiSense Score series
  (`get_metrics(ticker, metric_type="sentisense_score")`) alongside sentiment polarity.

## 0.42.0

### Added

- **`limit` and `offset` on `get_politician_member(slug)`**: `recentTrades` is one page of a
  member's history, and the server now returns 200 by default rather than everything. Most
  members have a few dozen disclosures and still arrive complete in one call; a handful have
  thousands, and the longest is over 12,000. Read `result.total_count` for the size of the
  whole history and page through it. Both arguments are keyword-only and optional, so calls
  that omit them send exactly the request they sent before.

  `result.profile` and `result.topTickers` describe the whole history whatever page you ask
  for, so `profile.totalTrades` does not shrink with a small `limit`.

### Fixed

- `PreviewResult.total_count` is no longer documented as `None` on full responses. Paged
  endpoints carry it on every tier: it is what tells you a page is not the whole set.

## 0.41.0

### Added

- **`get_politician_directory(q=None, limit=50, offset=0)`**: discover tracked members of
  Congress and the page slug identifying each, so you can find who to query without knowing
  slugs upfront. Summary only, no trade data; use `get_politician_member(slug)` for filings.
  Not tier-gated, so free and PRO callers get the same full response.

  Unlike `get_politician_members()`, the directory includes members who have **left
  Congress**, carrying `former` and `servedUntil`. That roster lists who currently holds
  office, so a former member was previously reachable only if you already knew their slug.

## 0.40.0

### Added

- **`priceAsOf` on `StockPrice` and `StockQuote`**: when the market data behind
  `currentPrice` is from, in Unix milliseconds. Read it for freshness rather than
  `timestamp`, which is when the response was served and therefore always reads as now.
  `None` means unknown age, not fresh. Appended to both dataclasses so positional
  construction keeps binding the same arguments.

### Fixed

- `timestamp` is no longer documented as the price's age; it is the serve time of the
  response.

## 0.39.0

### Added

- **Screener: `get_screener_fields()`, `list_screens()`, `run_screen()` and `run_etf_screen()`.**
  Filter the tracked universe on the SentiSense Score, attention, analyst consensus,
  technicals and price in a single query. A plan is `{"filters": [...], "sort": {...}}` with
  each filter `{"fieldName": ..., "op": ..., "value": ...}`, ANDed together; `limit` is passed
  as a keyword argument and rides next to the plan on the request body, defaulting to 100 and
  capping at 500. `tickers` is optional and omitting it screens the whole tracked universe.
  Results carry `matched`, the pre-limit count, so truncation is visible, and every row carries
  the full field set rather than only the fields you filtered on.
- **`list_screens()` returns the curated screens with a runnable plan each**, so
  `client.run_screen(screen.plan)` works with nothing to rebuild. Their filters identify the
  field with `field` rather than `fieldName`; both keys are accepted on the way in.
- **New types**: `ScreenerFieldCatalog`, `ScreenerField`, `ScreenerFieldOption`, `FeaturedScreen`,
  `ScreenerResults`, `ScreenerRow`, `EtfScreenerResults`, `EtfScreenerRow`.

### Notes

- Three field semantics are documented on the methods because guessing them wrong produces a
  screen that looks fine and means nothing: `ANALYST_RATING_MEAN` is inverted (1.0 is strong
  buy, so bullish is `LTE`), `MA_CROSS_STATE` is ordinal (`1` golden cross, `-1` death cross,
  `0` neither), and `SENTIMENT_DIRECTION` is the sign of the 7-day SentiSense Score with a
  neutral band of plus-or-minus 5, not a polarity reading.
- Filter the Score fields on the band edges 5 / 13 / 23. Polarity-scale values like `0.5`
  behave as "any positive score". Nulls never match in either direction.

## 0.38.0

### Added

- **Listing lifecycle on `StockPrice`: `listingStatus`, `delistedDate` and `delistingReason`.**
  `get_stock_price` and `get_stock_prices` now parse the same three fields `StockQuote`
  already carried, so a stock that has stopped trading no longer reads as an ordinary live
  price. They are `None` for an ordinarily listed stock, which is almost every ticker.
  `"DELISTED"` means every price field is frozen at the last trade before `delistedDate`,
  so do not render `changePercent` as a market move; `"PENDING_DELISTING"` means a merger
  or take-private is scheduled while the stock still trades, so the figures are current.
  The profile payload carries the same three keys.

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

---

The entries below cover releases that shipped before this file existed. They were
reconstructed from the commit history, so they are terser than the ones above and record
what changed rather than why. Only versions that reached PyPI are listed: several numbers
were bumped locally and their work went out inside the next published release, which is
noted where it happened.

## 0.27.0

- `youtube` added to the document source vocabulary.
- Documented the metric value scalar and the transaction-type vocabulary.

## 0.26.0

- `sort` parameter on `get_documents_by_source`.

## 0.25.0

- The search, source and entity document methods return a typed `DocumentSearchResponse`
  instead of a bare dict.
- Structured `assetMetadata` on congressional trades (asset kind, and option type, strike
  and expiry where the disclosure is an option).
- `movingAverage200Day` on `StockQuote`.
- 0.23.0 and 0.24.0 were bumped locally; their work went out in this release.

## 0.22.1

- Documented bare `tickers` against formatted `displayTickers` on `Story`.
- `get_sentiment_by_source` repointed to the v2 metrics endpoint. The method was later
  removed in 0.29.0 along with the rest of the v1 metrics family.
- Unit tests updated to match the typed response models.

## 0.22.0

- Earnings calendar endpoint and its types.
- `accessTier` on tracker listings.

## 0.21.1

- `list_trackers()` and `get_tracker()` for the unified trackers API.
- Fixed the preview unwrap on `get_tracker`, and added citation fields to tracker metrics.

## 0.21.0

- `list_institutions()` for institution discovery.
- `total_count` surfaced on `PreviewResult`.
- Fundamentals, short interest, float, short volume and knowledge base entity methods.
- `kbEntityId` on `SimilarStock` deprecated.
- 0.20.0 was bumped locally; its work went out in this release.

## 0.19.0

- `get_fundamentals_periods()`.
- `PreviewResult.data`, so list-wrapped endpoints have a payload accessor that does not
  depend on attribute delegation.
- Clarified the units of `weightCovered` on the ETF aggregates.

## 0.18.0

- ETF response cleanup: camelCase holdings keys, epoch-second timestamps, and
  `topContributors` always populated rather than tier-dependent.
- `StoryCluster.createdAt` renamed to `clusteredAt`, in epoch seconds.
- `Story.brokeAt` widened to `Optional[int]`.
- 0.16.1 and 0.17.0 were bumped locally; their work went out in this release.

## 0.16.0

- Typed the ETF aggregate responses.
- `PreviewResult` falls back to dict-style access when the wrapped payload is a plain dict,
  so the proxy stays transparent for endpoints without a typed model.

## 0.15.0

- ETF endpoints.
- `ExtendedHoursInfo`, and the current `currentPrice` semantics: it is always the
  regular-session price, with extended-hours activity in a nested object.
- Documented the `session` field on chart bars and the full timeframe set.
- 0.13.0 and 0.14.0 were bumped locally; their work went out in this release.

## 0.12.0

- Analyst ratings, company KPIs, institution detail, market mood, and the range, latest
  and user insight methods.
- Typed KPI models, with `list_kpi_coverage()` and `get_kpi_types()`.
- 0.11.0 was bumped locally; its work went out in this release.

## 0.10.1

- `get_stock_quote()` and `get_similar_stocks()`.
- Typed dataclasses with dict-style access preserved, and the preview envelope unwrapped
  automatically into `PreviewResult`.
- `avgClosePrice` and `dollarFlowUsd` on `InstitutionalFlow`.
- 0.10.0 was bumped locally; its work went out in this release.

## 0.9.0

- The same code as 0.8.1, published the same day. The bump promoted the congressional
  trading endpoints and the unified response wrapper from a patch to a minor release.

## 0.8.1

- Congressional trading endpoints.
- Automatic retry with backoff on failed requests.
- Corrected the return types and docstrings on the institutional and metrics methods.

## 0.8.0

- Insights endpoints.

## 0.7.0

- Insider trading endpoints.

## 0.6.0

- `get_market_summary()`.

## 0.5.0

- The v2 metrics methods `get_metrics()` and `get_metrics_distribution()`.

## 0.4.0

- Further document and story response type updates.

## 0.3.0

- Document and story endpoint response types updated.

## 0.2.1

- `get_institutional_flows()` corrected for the split inflows and outflows response shape.

## 0.2.0

- News, social media and sentiment endpoints.

## 0.1.0

- First release.
