"""Unit tests for how the client puts caller arguments into request paths.

Contracts gated here:

* Ordinary arguments (tickers, slugs, ids, metric types, CIKs passed as int) prepare
  exactly the URL earlier versions prepared, query string included. The expected URLs
  below were recorded from the previous release's client.
* Every path argument of every method is sent as exactly one path segment. ``?``, ``#``,
  ``/``, a space, ``%``, an already-encoded ``%2F`` and non-ASCII text are
  percent-encoded, so a value can never move the request to another route, turn the rest
  of the path into a query string or drop it as a fragment.
* ``.`` and ``..`` raise ``ValueError`` naming the argument, before any request is sent.
  An empty value is still sent as it always was, and the API answers it.
* No request path in the client interpolates an argument without encoding it.

``get_metrics_slices`` has its own, stricter tests in ``test_metric_slices.py``.
"""

import inspect
import re
from collections import Counter
from unittest.mock import patch
from urllib.parse import urlsplit

import pytest
import requests

import sentisense.client as client_module
from sentisense import SentiSenseClient

BASE = "https://app.sentisense.ai"


class _Sent(Exception):
    """Raised by the mocked transport once it has seen the request."""


def _prepared_url(method, *args, **kwargs):
    """The URL requests would put on the wire for this call. Nothing is sent."""
    client = SentiSenseClient("test-api-key")
    seen = {}

    def transport(url, **kw):
        seen["url"], seen["params"] = url, kw.get("params")
        raise _Sent

    with patch.object(client.session, "get", side_effect=transport):
        with pytest.raises(_Sent):
            getattr(client, method)(*args, **kwargs)
    return requests.Request("GET", seen["url"], params=seen["params"]).prepare().url


def _label(method, args, kwargs):
    parts = [repr(a) for a in args] + ["%s=%r" % kv for kv in kwargs.items()]
    return "%s(%s)" % (method, ", ".join(parts))


# (method, args, kwargs, path and query the previous release prepared)
ORDINARY = [
    ('get_stock_quote', ('AAPL',), {}, '/api/v1/stocks/AAPL/quote'),
    ('get_stock_quote', ('BRK.B',), {}, '/api/v1/stocks/BRK.B/quote'),
    ('get_stock_quote', ('BF-B',), {}, '/api/v1/stocks/BF-B/quote'),
    ('get_stock_quote', ('SPY',), {}, '/api/v1/stocks/SPY/quote'),
    ('get_stock_quote', ('^VIX',), {}, '/api/v1/stocks/%5EVIX/quote'),
    ('get_stock_quote', ('',), {}, '/api/v1/stocks//quote'),
    ('get_stock_quote', (' ',), {}, '/api/v1/stocks/%20/quote'),
    ('get_stock_profile', ('AAPL',), {}, '/api/v1/stocks/AAPL/profile'),
    ('get_stock_profile', ('BRK.B',), {}, '/api/v1/stocks/BRK.B/profile'),
    ('get_stock_profile', ('BF-B',), {}, '/api/v1/stocks/BF-B/profile'),
    ('get_stock_profile', ('SPY',), {}, '/api/v1/stocks/SPY/profile'),
    ('get_stock_sentiment', ('AAPL',), {}, '/api/v1/stocks/AAPL/sentiment'),
    ('get_stock_sentiment', ('BRK.B',), {}, '/api/v1/stocks/BRK.B/sentiment'),
    ('get_stock_sentiment', ('BF-B',), {}, '/api/v1/stocks/BF-B/sentiment'),
    ('get_stock_sentiment', ('SPY',), {}, '/api/v1/stocks/SPY/sentiment'),
    ('get_stock_entities', ('AAPL',), {}, '/api/v1/stocks/AAPL/entities'),
    ('get_stock_entities', ('BRK.B',), {}, '/api/v1/stocks/BRK.B/entities'),
    ('get_stock_entities', ('BF-B',), {}, '/api/v1/stocks/BF-B/entities'),
    ('get_stock_graph', ('AAPL',), {}, '/api/v1/stocks/AAPL/graph?depth=1&cap=75'),
    ('get_stock_graph', ('brk.b',), {'depth': 2, 'cap': 50}, '/api/v1/stocks/BRK.B/graph?depth=2&cap=50'),
    ('get_stock_graph', ('BF-B',), {}, '/api/v1/stocks/BF-B/graph?depth=1&cap=75'),
    ('get_stock_ai_summary', ('AAPL',), {}, '/api/v1/stocks/AAPL/ai-summary?depth=basic'),
    ('get_stock_ai_summary', ('BRK.B',), {'depth': 'deep'}, '/api/v1/stocks/BRK.B/ai-summary?depth=deep'),
    ('get_stock_ai_summary', ('BF-B',), {}, '/api/v1/stocks/BF-B/ai-summary?depth=basic'),
    ('get_stock_metrics_breakdown', ('AAPL', 'sentiment', 1767225600000, 1769904000000), {}, '/api/v1/stocks/AAPL/metrics/sentiment/breakdown?startTime=1767225600000&endTime=1769904000000'),
    ('get_stock_metrics_breakdown', ('BRK.B', 'mentions', 1767225600000, 1769904000000), {}, '/api/v1/stocks/BRK.B/metrics/mentions/breakdown?startTime=1767225600000&endTime=1769904000000'),
    ('get_stock_metrics_breakdown', ('BF-B', 'sentiment', 1767225600000, 1769904000000), {}, '/api/v1/stocks/BF-B/metrics/sentiment/breakdown?startTime=1767225600000&endTime=1769904000000'),
    ('get_similar_stocks', ('AAPL',), {'limit': 10}, '/api/v1/stocks/AAPL/similar?limit=10'),
    ('get_similar_stocks', ('BRK.B',), {}, '/api/v1/stocks/BRK.B/similar?limit=5'),
    ('get_similar_stocks', ('BF-B',), {}, '/api/v1/stocks/BF-B/similar?limit=5'),
    ('get_stock_etfs', ('AAPL',), {}, '/api/v1/stocks/AAPL/etfs'),
    ('get_stock_etfs', ('BRK.B',), {'limit': 5}, '/api/v1/stocks/BRK.B/etfs?limit=5'),
    ('get_stock_etfs', ('BF-B',), {}, '/api/v1/stocks/BF-B/etfs'),
    ('get_stock_holders', ('AAPL',), {}, '/api/v1/institutional/holders/AAPL'),
    ('get_stock_holders', ('BRK.B',), {'report_date': '2025-12-31'}, '/api/v1/institutional/holders/BRK.B?reportDate=2025-12-31'),
    ('get_stock_holders', ('BF-B',), {'limit': 50, 'offset': 0, 'sort_by': 'valueUsd', 'sort_dir': 'desc'}, '/api/v1/institutional/holders/BF-B?limit=50&offset=0&sortBy=valueUsd&sortDir=desc'),
    ('get_stock_holders', ('SPY',), {}, '/api/v1/institutional/holders/SPY'),
    ('get_stock_holders_history', ('AAPL',), {'quarters': 8}, '/api/v1/institutional/holders/AAPL/history?quarters=8'),
    ('get_stock_holders_history', ('BRK.B',), {}, '/api/v1/institutional/holders/BRK.B/history'),
    ('get_stock_holders_history', ('BF-B',), {}, '/api/v1/institutional/holders/BF-B/history'),
    ('get_institution_detail', ('Berkshire-Hathaway',), {}, '/api/v1/institutional/institution/Berkshire-Hathaway'),
    ('get_institution_detail', ('berkshire-hathaway',), {'limit': 10, 'sort_by': 'portfolioWeight'}, '/api/v1/institutional/institution/berkshire-hathaway?limit=10&sortBy=portfolioWeight'),
    ('get_institution_detail', ('Renaissance-Technologies',), {'change_type': ['NEW', 'INCREASED'], 'q': 'NV', 'min_weight': 0.5, 'limit': 20}, '/api/v1/institutional/institution/Renaissance-Technologies?limit=20&changeType=NEW%2CINCREASED&q=NV&minWeight=0.5'),
    ('get_institution_detail', ('1067983',), {}, '/api/v1/institutional/institution/1067983'),
    ('get_institution_detail', (1067983,), {}, '/api/v1/institutional/institution/1067983'),
    ('get_institution_detail', ('0001067983',), {}, '/api/v1/institutional/institution/0001067983'),
    ('get_institution_detail', ('Berkshire Hathaway',), {}, '/api/v1/institutional/institution/Berkshire%20Hathaway'),
    ('get_institution_detail', ('',), {}, '/api/v1/institutional/institution/'),
    ('get_institution_history', ('Renaissance-Technologies',), {'quarters': 8, 'tickers': ['NVDA', 'META']}, '/api/v1/institutional/institution/Renaissance-Technologies/history?quarters=8&tickers=NVDA%2CMETA'),
    ('get_institution_history', (1067983,), {}, '/api/v1/institutional/institution/1067983/history'),
    ('get_institution_history', ('berkshire-hathaway',), {'tickers': 'AAPL,BRK.B'}, '/api/v1/institutional/institution/berkshire-hathaway/history?tickers=AAPL%2CBRK.B'),
    ('get_earnings_summaries', ('AAPL',), {'limit': 4}, '/api/v1/stocks/AAPL/earnings-summaries?limit=4'),
    ('get_earnings_summaries', ('brk.b',), {}, '/api/v1/stocks/BRK.B/earnings-summaries'),
    ('get_earnings_summaries', ('BF-B',), {}, '/api/v1/stocks/BF-B/earnings-summaries'),
    ('get_earnings_summaries', ('GOOGL',), {}, '/api/v1/stocks/GOOGL/earnings-summaries'),
    ('get_earnings_reactions', ('AAPL',), {}, '/api/v1/stocks/AAPL/earnings/reactions'),
    ('get_earnings_reactions', ('BRK.B',), {}, '/api/v1/stocks/BRK.B/earnings/reactions'),
    ('get_earnings_reactions', ('bf-b',), {}, '/api/v1/stocks/BF-B/earnings/reactions'),
    ('get_stock_options_summary', ('NVDA',), {}, '/api/v1/stocks/NVDA/options/summary'),
    ('get_stock_options_summary', ('SPY',), {}, '/api/v1/stocks/SPY/options/summary'),
    ('get_stock_options_summary', ('BRK.B',), {}, '/api/v1/stocks/BRK.B/options/summary'),
    ('get_stock_options_summary', ('aapl',), {}, '/api/v1/stocks/AAPL/options/summary'),
    ('get_stock_options_history', ('NVDA',), {'window': '2y'}, '/api/v1/stocks/NVDA/options/history?window=2y'),
    ('get_stock_options_history', ('SPY',), {}, '/api/v1/stocks/SPY/options/history?window=1y'),
    ('get_stock_options_history', ('BF-B',), {}, '/api/v1/stocks/BF-B/options/history?window=1y'),
    ('get_stock_options_intraday_history', ('NVDA',), {'session': '2026-11-17'}, '/api/v1/stocks/NVDA/options/intraday-history?session=2026-11-17'),
    ('get_stock_options_intraday_history', ('spy',), {}, '/api/v1/stocks/SPY/options/intraday-history'),
    ('get_stock_options_intraday_history', ('BRK.B',), {}, '/api/v1/stocks/BRK.B/options/intraday-history'),
    ('get_rating', ('AAPL',), {}, '/api/v1/rating/AAPL'),
    ('get_rating', ('brk.b',), {}, '/api/v1/rating/BRK.B'),
    ('get_rating', ('BF-B',), {}, '/api/v1/rating/BF-B'),
    ('get_rating', ('',), {}, '/api/v1/rating/'),
    ('get_insider_trades', ('AAPL',), {'lookback_days': 30}, '/api/v1/insider/trades/AAPL?lookbackDays=30'),
    ('get_insider_trades', ('BRK.B',), {}, '/api/v1/insider/trades/BRK.B?lookbackDays=90'),
    ('get_insider_trades', ('BF-B',), {}, '/api/v1/insider/trades/BF-B?lookbackDays=90'),
    ('get_politician_filings', ('NVDA',), {}, '/api/v1/politicians/filings/NVDA?lookbackDays=90'),
    ('get_politician_filings', ('BRK.B',), {'lookback_days': 365}, '/api/v1/politicians/filings/BRK.B?lookbackDays=365'),
    ('get_politician_filings', ('bf-b',), {}, '/api/v1/politicians/filings/BF-B?lookbackDays=90'),
    ('get_politician_member', ('Nancy-Pelosi',), {}, '/api/v1/politicians/member/Nancy-Pelosi'),
    ('get_politician_member', ('nancy-pelosi',), {}, '/api/v1/politicians/member/nancy-pelosi'),
    ('get_politician_member', ('Ro-Khanna',), {'limit': 500, 'offset': 500}, '/api/v1/politicians/member/Ro-Khanna?limit=500&offset=500'),
    ('get_stock_insights', ('AAPL',), {'urgency': 'high'}, '/api/v1/insights/stock/AAPL?urgency=high'),
    ('get_stock_insights', ('BRK.B',), {'insight_type': 'insider_buy_signal'}, '/api/v1/insights/stock/BRK.B?insightType=insider_buy_signal'),
    ('get_stock_insights', ('BF-B',), {}, '/api/v1/insights/stock/BF-B'),
    ('get_insight_types', ('AAPL',), {}, '/api/v1/insights/stock/AAPL/types'),
    ('get_insight_types', ('BRK.B',), {}, '/api/v1/insights/stock/BRK.B/types'),
    ('get_insight_types', ('bf-b',), {}, '/api/v1/insights/stock/BF-B/types'),
    ('get_stock_insights_range', ('AAPL', '2026-10-01', '2026-10-31'), {}, '/api/v1/insights/stock/AAPL/range?startDate=2026-10-01&endDate=2026-10-31'),
    ('get_stock_insights_range', ('BRK.B', '2026-01-01', '2026-03-31'), {'urgency': 'medium'}, '/api/v1/insights/stock/BRK.B/range?startDate=2026-01-01&endDate=2026-03-31&urgency=medium'),
    ('get_stock_insights_range', ('BF-B', '2026-10-01', '2026-10-31'), {}, '/api/v1/insights/stock/BF-B/range?startDate=2026-10-01&endDate=2026-10-31'),
    ('get_analyst_consensus', ('AAPL',), {}, '/api/v1/analyst/AAPL/consensus'),
    ('get_analyst_consensus', ('BRK.B',), {}, '/api/v1/analyst/BRK.B/consensus'),
    ('get_analyst_consensus', ('BF-B',), {}, '/api/v1/analyst/BF-B/consensus'),
    ('get_analyst_consensus_history', ('AAPL',), {'from_date': '2026-08-01', 'to_date': '2026-10-31', 'limit': 90}, '/api/v1/analyst/AAPL/consensus/history?from=2026-08-01&to=2026-10-31&limit=90'),
    ('get_analyst_consensus_history', ('brk.b',), {}, '/api/v1/analyst/BRK.B/consensus/history'),
    ('get_analyst_called_it', ('AAPL',), {'limit': 5}, '/api/v1/analyst/AAPL/called-it?limit=5'),
    ('get_analyst_called_it', ('BF-B',), {}, '/api/v1/analyst/BF-B/called-it'),
    ('get_analyst_actions', ('AAPL',), {}, '/api/v1/analyst/AAPL/actions?lookbackDays=90'),
    ('get_analyst_actions', ('BRK.B',), {'lookback_days': 30}, '/api/v1/analyst/BRK.B/actions?lookbackDays=30'),
    ('get_analyst_estimates', ('AAPL',), {}, '/api/v1/analyst/AAPL/estimates'),
    ('get_analyst_estimates', ('BRK.B',), {}, '/api/v1/analyst/BRK.B/estimates'),
    ('get_analyst_estimates', ('BF-B',), {}, '/api/v1/analyst/BF-B/estimates'),
    ('get_analyst_coverage', ('AMD',), {'lookback_days': 365}, '/api/v1/analyst/AMD/coverage?lookbackDays=365'),
    ('get_analyst_coverage', ('BRK.B',), {}, '/api/v1/analyst/BRK.B/coverage'),
    ('get_analyst_profile', ('dan-ives',), {}, '/api/v1/analyst/people/dan-ives'),
    ('get_analyst_profile', ('gil-luria',), {}, '/api/v1/analyst/people/gil-luria'),
    ('get_analyst_calls', ('dan-ives',), {'limit': 25, 'offset': 25}, '/api/v1/analyst/people/dan-ives/calls?limit=25&offset=25'),
    ('get_analyst_calls', ('gil-luria',), {}, '/api/v1/analyst/people/gil-luria/calls'),
    ('get_etf_holdings', ('QQQ',), {}, '/api/v1/etfs/QQQ/holdings'),
    ('get_etf_holdings', ('spy',), {}, '/api/v1/etfs/SPY/holdings'),
    ('get_etf_holdings', ('XLK',), {}, '/api/v1/etfs/XLK/holdings'),
    ('get_etf_quote', ('SPY',), {}, '/api/v1/etfs/SPY/quote'),
    ('get_etf_quote', ('qqq',), {}, '/api/v1/etfs/QQQ/quote'),
    ('get_etf_analyst_aggregate', ('SPY',), {}, '/api/v1/etfs/SPY/aggregates/analyst'),
    ('get_etf_analyst_aggregate', ('QQQ',), {}, '/api/v1/etfs/QQQ/aggregates/analyst'),
    ('get_etf_insider_aggregate', ('SPY',), {'lookback_days': 60}, '/api/v1/etfs/SPY/aggregates/insider?lookbackDays=60'),
    ('get_etf_insider_aggregate', ('xlk',), {}, '/api/v1/etfs/XLK/aggregates/insider?lookbackDays=30'),
    ('get_etf_sentiment_aggregate', ('SPY',), {}, '/api/v1/etfs/SPY/aggregates/sentiment'),
    ('get_etf_sentiment_aggregate', ('QQQ',), {}, '/api/v1/etfs/QQQ/aggregates/sentiment'),
    ('get_company_kpis', ('AAPL',), {}, '/api/v1/stocks/AAPL/kpis'),
    ('get_company_kpis', ('brk.b',), {}, '/api/v1/stocks/BRK.B/kpis'),
    ('get_company_kpis', ('BF-B',), {}, '/api/v1/stocks/BF-B/kpis'),
    ('get_kpi_types', ('AAPL',), {}, '/api/v1/stocks/AAPL/kpis/types'),
    ('get_kpi_types', ('BRK.B',), {}, '/api/v1/stocks/BRK.B/kpis/types'),
    ('get_documents_by_ticker', ('AAPL',), {'source': 'news', 'days': 7, 'limit': 20}, '/api/v1/documents/ticker/AAPL?source=news&days=7&limit=20'),
    ('get_documents_by_ticker', ('BRK.B',), {'hours': 24}, '/api/v1/documents/ticker/BRK.B?hours=24'),
    ('get_documents_by_ticker', ('BF-B',), {}, '/api/v1/documents/ticker/BF-B'),
    ('get_documents_by_ticker', ('SPY',), {}, '/api/v1/documents/ticker/SPY'),
    ('get_documents_by_ticker_range', ('AAPL', '2025-01-01', '2025-01-31'), {'source': 'reddit', 'limit': 50}, '/api/v1/documents/ticker/AAPL/range?startDate=2025-01-01&endDate=2025-01-31&source=reddit&limit=50'),
    ('get_documents_by_ticker_range', ('BRK.B', '2025-01-01', '2025-01-31'), {}, '/api/v1/documents/ticker/BRK.B/range?startDate=2025-01-01&endDate=2025-01-31'),
    ('get_documents_by_entity', ('Tim-Cook',), {'days': 14}, '/api/v1/documents/entity/Tim-Cook?days=14'),
    ('get_documents_by_entity', ('Nancy-Pelosi',), {}, '/api/v1/documents/entity/Nancy-Pelosi'),
    ('get_documents_by_entity', ('Berkshire-Hathaway',), {'source': 'x'}, '/api/v1/documents/entity/Berkshire-Hathaway?source=x'),
    ('get_documents_by_source', ('news',), {'sort': 'top'}, '/api/v1/documents/source/news?sort=top'),
    ('get_documents_by_source', ('reddit',), {'hours': 6}, '/api/v1/documents/source/reddit?hours=6'),
    ('get_documents_by_source', ('x',), {}, '/api/v1/documents/source/x'),
    ('get_documents_by_source', ('substack',), {}, '/api/v1/documents/source/substack'),
    ('get_documents_by_source', ('youtube',), {'limit': 10}, '/api/v1/documents/source/youtube?limit=10'),
    ('get_story_detail', ('boj-lifts-rates-09182026',), {}, '/api/v1/documents/stories/boj-lifts-rates-09182026'),
    ('get_story_detail', ('4815162342',), {}, '/api/v1/documents/stories/4815162342'),
    ('get_story_detail', (4815162342,), {}, '/api/v1/documents/stories/4815162342'),
    ('get_stories_by_ticker', ('AAPL',), {'limit': 10}, '/api/v1/documents/stories/ticker/AAPL?limit=10'),
    ('get_stories_by_ticker', ('BRK.B',), {}, '/api/v1/documents/stories/ticker/BRK.B'),
    ('get_stories_by_ticker', ('BF-B',), {}, '/api/v1/documents/stories/ticker/BF-B'),
    ('get_metrics', ('AAPL',), {}, '/api/v2/metrics/entity/AAPL/metric/sentiment'),
    ('get_metrics', ('BRK.B', 'mentions'), {'start_time': 1767225600000, 'end_time': 1769904000000}, '/api/v2/metrics/entity/BRK.B/metric/mentions?startTime=1767225600000&endTime=1769904000000'),
    ('get_metrics', ('Nancy-Pelosi', 'sentisense_score'), {}, '/api/v2/metrics/entity/Nancy-Pelosi/metric/sentisense_score'),
    ('get_metrics', ('Tim-Cook', 'social_dominance'), {}, '/api/v2/metrics/entity/Tim-Cook/metric/social_dominance'),
    ('get_metrics', ('Instagram', 'app_rating'), {}, '/api/v2/metrics/entity/Instagram/metric/app_rating'),
    ('get_metrics', ('BF-B', 'sentisense_rating'), {'max_data_points': 30}, '/api/v2/metrics/entity/BF-B/metric/sentisense_rating?maxDataPoints=30'),
    ('get_metrics', ('SPY', 'sentiment'), {}, '/api/v2/metrics/entity/SPY/metric/sentiment'),
    ('get_metrics', ('Tim Cook', 'sentiment'), {}, '/api/v2/metrics/entity/Tim%20Cook/metric/sentiment'),
    ('get_metrics', ('', 'sentiment'), {}, '/api/v2/metrics/entity//metric/sentiment'),
    ('get_metrics_distribution', ('AAPL',), {}, '/api/v2/metrics/entity/AAPL/distribution/mentions?dimension=source'),
    ('get_metrics_distribution', ('BRK.B', 'sentiment'), {'dimension': 'source', 'start_time': 1767225600000, 'end_time': 1769904000000}, '/api/v2/metrics/entity/BRK.B/distribution/sentiment?dimension=source&startTime=1767225600000&endTime=1769904000000'),
    ('get_metrics_distribution', ('Nancy-Pelosi', 'creators'), {}, '/api/v2/metrics/entity/Nancy-Pelosi/distribution/creators?dimension=source'),
    ('get_metrics_slices', ('AAPL', 'mentions'), {}, '/api/v2/metrics/entity/AAPL/metric/mentions/slices'),
    ('get_metrics_slices', ('BRK.B', 'sentiment'), {}, '/api/v2/metrics/entity/BRK.B/metric/sentiment/slices'),
    ('get_metrics_slices', ('Tim-Cook', 'sentisense_score'), {}, '/api/v2/metrics/entity/Tim-Cook/metric/sentisense_score/slices'),
    ('get_index', ('fed-sentiment',), {}, '/api/v1/indexes/fed-sentiment'),
    ('get_index', ('market-mood',), {}, '/api/v1/indexes/market-mood'),
    ('get_index', ('ai-sentiment',), {}, '/api/v1/indexes/ai-sentiment'),
    ('get_index', ('fear-and-greed',), {}, '/api/v1/indexes/fear-and-greed'),
    ('get_index_history', ('fed-sentiment',), {'days': 90}, '/api/v1/indexes/fed-sentiment/history?days=90'),
    ('get_index_history', ('market-mood',), {}, '/api/v1/indexes/market-mood/history?days=180'),
    ('get_tracker', ('institution-concentration',), {}, '/api/v1/trackers/institution-concentration'),
    ('get_tracker', ('market-heatmap',), {'scope': 'nasdaq100'}, '/api/v1/trackers/market-heatmap?scope=nasdaq100'),
    ('get_tracker', ('hedge-fund-reported-returns',), {'category': ''}, '/api/v1/trackers/hedge-fund-reported-returns?category='),
    ('get_tracker', ('institution-concentration',), {'filter': {'state': 'TX', 'category': 'local'}}, '/api/v1/trackers/institution-concentration?filter=state%3ATX%2Ccategory%3Alocal'),
    ('get_tracker', ('',), {}, '/api/v1/trackers/'),
]


class TestOrdinaryArgumentsAreSentAsBefore:
    @pytest.mark.parametrize(
        "method, args, kwargs, expected",
        [pytest.param(*row, id=_label(*row[:3])) for row in ORDINARY],
    )
    def test_prepared_url_is_unchanged(self, method, args, kwargs, expected):
        assert _prepared_url(method, *args, **kwargs) == BASE + expected


V = object()  # marks the argument under test

# (method, args, kwargs, argument name, path with {} where the argument goes, query)
SLOTS = [
    ("get_stock_quote", (V,), {}, "ticker", "/api/v1/stocks/{}/quote", ""),
    ("get_stock_profile", (V,), {}, "ticker", "/api/v1/stocks/{}/profile", ""),
    ("get_stock_sentiment", (V,), {}, "ticker", "/api/v1/stocks/{}/sentiment", ""),
    ("get_stock_entities", (V,), {}, "ticker", "/api/v1/stocks/{}/entities", ""),
    ("get_stock_graph", (V,), {}, "ticker", "/api/v1/stocks/{}/graph", "depth=1&cap=75"),
    ("get_stock_ai_summary", (V,), {}, "ticker", "/api/v1/stocks/{}/ai-summary", "depth=basic"),
    ("get_stock_metrics_breakdown", (V, "sentiment", 1, 2), {}, "ticker",
     "/api/v1/stocks/{}/metrics/sentiment/breakdown", "startTime=1&endTime=2"),
    ("get_stock_metrics_breakdown", ("EXMP", V, 1, 2), {}, "metric_type",
     "/api/v1/stocks/EXMP/metrics/{}/breakdown", "startTime=1&endTime=2"),
    ("get_similar_stocks", (V,), {}, "ticker", "/api/v1/stocks/{}/similar", "limit=5"),
    ("get_stock_etfs", (V,), {}, "ticker", "/api/v1/stocks/{}/etfs", ""),
    ("get_stock_holders", (V,), {}, "ticker", "/api/v1/institutional/holders/{}", ""),
    ("get_stock_holders_history", (V,), {}, "ticker", "/api/v1/institutional/holders/{}/history", ""),
    ("get_institution_detail", (V,), {}, "slug_or_cik", "/api/v1/institutional/institution/{}", ""),
    ("get_institution_history", (V,), {}, "slug_or_cik", "/api/v1/institutional/institution/{}/history", ""),
    ("get_earnings_summaries", (V,), {}, "ticker", "/api/v1/stocks/{}/earnings-summaries", ""),
    ("get_earnings_reactions", (V,), {}, "ticker", "/api/v1/stocks/{}/earnings/reactions", ""),
    ("get_stock_options_summary", (V,), {}, "ticker", "/api/v1/stocks/{}/options/summary", ""),
    ("get_stock_options_history", (V,), {}, "ticker", "/api/v1/stocks/{}/options/history", "window=1y"),
    ("get_stock_options_intraday_history", (V,), {}, "ticker", "/api/v1/stocks/{}/options/intraday-history", ""),
    ("get_rating", (V,), {}, "ticker", "/api/v1/rating/{}", ""),
    ("get_insider_trades", (V,), {}, "ticker", "/api/v1/insider/trades/{}", "lookbackDays=90"),
    ("get_politician_filings", (V,), {}, "ticker", "/api/v1/politicians/filings/{}", "lookbackDays=90"),
    ("get_politician_member", (V,), {}, "slug", "/api/v1/politicians/member/{}", ""),
    ("get_stock_insights", (V,), {}, "ticker", "/api/v1/insights/stock/{}", ""),
    ("get_insight_types", (V,), {}, "ticker", "/api/v1/insights/stock/{}/types", ""),
    ("get_stock_insights_range", (V, "2026-10-01", "2026-10-31"), {}, "ticker",
     "/api/v1/insights/stock/{}/range", "startDate=2026-10-01&endDate=2026-10-31"),
    ("get_analyst_consensus", (V,), {}, "ticker", "/api/v1/analyst/{}/consensus", ""),
    ("get_analyst_consensus_history", (V,), {}, "ticker", "/api/v1/analyst/{}/consensus/history", ""),
    ("get_analyst_called_it", (V,), {}, "ticker", "/api/v1/analyst/{}/called-it", ""),
    ("get_analyst_actions", (V,), {}, "ticker", "/api/v1/analyst/{}/actions", "lookbackDays=90"),
    ("get_analyst_estimates", (V,), {}, "ticker", "/api/v1/analyst/{}/estimates", ""),
    ("get_analyst_coverage", (V,), {}, "ticker", "/api/v1/analyst/{}/coverage", ""),
    ("get_analyst_profile", (V,), {}, "slug", "/api/v1/analyst/people/{}", ""),
    ("get_analyst_calls", (V,), {}, "slug", "/api/v1/analyst/people/{}/calls", ""),
    ("get_etf_holdings", (V,), {}, "ticker", "/api/v1/etfs/{}/holdings", ""),
    ("get_etf_quote", (V,), {}, "ticker", "/api/v1/etfs/{}/quote", ""),
    ("get_etf_analyst_aggregate", (V,), {}, "ticker", "/api/v1/etfs/{}/aggregates/analyst", ""),
    ("get_etf_insider_aggregate", (V,), {}, "ticker", "/api/v1/etfs/{}/aggregates/insider", "lookbackDays=30"),
    ("get_etf_sentiment_aggregate", (V,), {}, "ticker", "/api/v1/etfs/{}/aggregates/sentiment", ""),
    ("get_company_kpis", (V,), {}, "ticker", "/api/v1/stocks/{}/kpis", ""),
    ("get_kpi_types", (V,), {}, "ticker", "/api/v1/stocks/{}/kpis/types", ""),
    ("get_documents_by_ticker", (V,), {}, "ticker", "/api/v1/documents/ticker/{}", ""),
    ("get_documents_by_ticker_range", (V, "2025-01-01", "2025-01-31"), {}, "ticker",
     "/api/v1/documents/ticker/{}/range", "startDate=2025-01-01&endDate=2025-01-31"),
    ("get_documents_by_entity", (V,), {}, "entity_id", "/api/v1/documents/entity/{}", ""),
    ("get_documents_by_source", (V,), {}, "source", "/api/v1/documents/source/{}", ""),
    ("get_story_detail", (V,), {}, "story_id", "/api/v1/documents/stories/{}", ""),
    ("get_stories_by_ticker", (V,), {}, "ticker", "/api/v1/documents/stories/ticker/{}", ""),
    ("get_metrics", (V, "sentiment"), {}, "symbol", "/api/v2/metrics/entity/{}/metric/sentiment", ""),
    ("get_metrics", ("EXMP", V), {}, "metric_type", "/api/v2/metrics/entity/EXMP/metric/{}", ""),
    ("get_metrics_distribution", (V, "mentions"), {}, "symbol",
     "/api/v2/metrics/entity/{}/distribution/mentions", "dimension=source"),
    ("get_metrics_distribution", ("EXMP", V), {}, "metric_type",
     "/api/v2/metrics/entity/EXMP/distribution/{}", "dimension=source"),
    ("get_index", (V,), {}, "index_id", "/api/v1/indexes/{}", ""),
    ("get_index_history", (V,), {}, "index_id", "/api/v1/indexes/{}/history", "days=180"),
    ("get_tracker", (V,), {}, "tracker_id", "/api/v1/trackers/{}", ""),
]


_SLOTS_PER_METHOD = Counter(row[0] for row in SLOTS)


def _fill(args, value):
    return tuple(value if a is V else a for a in args)


def _slot_id(row):
    return row[0] if _SLOTS_PER_METHOD[row[0]] == 1 else "%s[%s]" % (row[0], row[3])


SLOT_PARAMS = [pytest.param(*row, id=_slot_id(row)) for row in SLOTS]

# Every value here reads the same upper-cased, because several methods upper-case a
# ticker before sending it.
RESERVED = [
    ("EX?MP", "EX%3FMP"),
    ("EX#MP", "EX%23MP"),
    ("EX/MP", "EX%2FMP"),
    ("EX MP", "EX%20MP"),
    ("EX%MP", "EX%25MP"),
    ("EX%2FMP", "EX%252FMP"),
    ("EX€MP", "EX%E2%82%ACMP"),
]


class TestEveryPathArgumentStaysInItsSegment:
    @pytest.mark.parametrize(
        "value, segment",
        RESERVED,
        ids=["question-mark", "hash", "slash", "space", "percent", "encoded-slash", "non-ascii"],
    )
    @pytest.mark.parametrize("method, args, kwargs, name, path, query", SLOT_PARAMS)
    def test_reserved_characters_are_encoded(self, method, args, kwargs, name, path, query, value, segment):
        parts = urlsplit(_prepared_url(method, *_fill(args, value), **kwargs))
        assert parts.path == path.format(segment)
        assert parts.query == query
        assert parts.fragment == ""

    @pytest.mark.parametrize("value", [".", ".."], ids=["dot", "dot-dot"])
    @pytest.mark.parametrize("method, args, kwargs, name, path, query", SLOT_PARAMS)
    def test_dot_segments_raise_before_any_request(self, method, args, kwargs, name, path, query, value):
        client = SentiSenseClient("test-api-key")
        with patch.object(client.session, "get") as get:
            with pytest.raises(ValueError) as caught:
                getattr(client, method)(*_fill(args, value), **kwargs)
        get.assert_not_called()
        assert str(caught.value) == "%s must not be '.' or '..'; got %r" % (name, value)

    @pytest.mark.parametrize(
        "value", ["", "...", ".X", "A..B"], ids=["empty", "three-dots", "dot-prefix", "inner-dots"]
    )
    @pytest.mark.parametrize("method, args, kwargs, name, path, query", SLOT_PARAMS)
    def test_other_values_are_sent_as_given(self, method, args, kwargs, name, path, query, value):
        parts = urlsplit(_prepared_url(method, *_fill(args, value), **kwargs))
        assert parts.path == path.format(value)
        assert parts.query == query


# An f-string request path, in either quote style.
_PATH_FSTRING = re.compile(r"""f(["'])(/api/(?:(?!\1).)*)\1""")


class TestNoRequestPathInterpolatesRawArguments:
    def test_every_path_placeholder_is_encoded(self):
        paths = [m.group(2) for m in _PATH_FSTRING.finditer(inspect.getsource(client_module))]
        assert paths, "no request paths found; the pattern needs updating"
        assert [p for p in paths if re.search(r"\{(?!_segment\()", p)] == []

    def test_no_path_is_built_another_way(self):
        source = inspect.getsource(client_module)
        assert re.findall(r"""["']/api/[^"']*["']\s*(?:\+|%|\.format\()""", source) == []

    def test_every_encoded_argument_is_in_the_table(self):
        in_source = Counter()
        for name, fn in inspect.getmembers(SentiSenseClient, inspect.isfunction):
            if not name.startswith("_") and name != "get_metrics_slices":
                in_source[name] = len(re.findall(r"_segment\(", inspect.getsource(fn)))
        assert +in_source == _SLOTS_PER_METHOD
