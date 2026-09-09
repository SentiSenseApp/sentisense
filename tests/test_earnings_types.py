"""Unit tests for the typed earnings methods.

Two contracts are worth gating here. First, the quarter arrives in two shapes on
the same envelope: a PRO quarter carries the bodies (``summaryMd``, guidance,
call summary), a FREE quarter replaces them with section titles and a guidance
direction. A client that reads ``summaryMd`` without checking ``is_preview``
silently renders an empty panel for every free key, so both shapes are parsed
here from realistic payloads.

Second, absence is explicit rather than implied. ``hasTranscript`` is ``False``
on a quarter with no call summary instead of the field being dropped, and the
optional ``yoy`` on a KPI card is ``None`` rather than an empty string. Coercing
either loses information the API deliberately sends. The reaction, statistics,
and ranked fixtures likewise preserve nullable fields, nested blocks, tier
metadata, and full-window counts.
"""

from unittest.mock import MagicMock, patch

import pytest

from sentisense import SentiSenseClient
from sentisense.types import (
    EarningsKpiHighlight,
    EarningsOutcomeStatistics,
    EarningsQuarter,
    EarningsReaction,
    EarningsReactions,
    EarningsSource,
    EarningsStatistics,
    EarningsStatisticsBaseline,
    RankedEarnings,
    RankedReportedEarnings,
    RankedUpcomingEarnings,
    RecentEarningsEntry,
)


@pytest.fixture
def client():
    return SentiSenseClient("test-api-key")


def _mock_response(json_data=None):
    resp = MagicMock()
    resp.status_code = 200
    resp.ok = True
    resp.json.return_value = json_data or {}
    return resp


PRO_QUARTER = {
    "fiscalPeriod": "Q2 2026",
    "reportDate": "2026-07-31",
    "headline": "Revenue grew 20% and operating income outpaced it",
    "summaryMd": "- Revenue was $200.6B, up 20% year over year",
    "kpiHighlights": [
        {"label": "Net Sales", "value": "$200.6B", "yoy": "+20% YoY"},
        {"label": "Operating income", "value": "$27.5B", "yoy": "+43% YoY"},
    ],
    "guidance": "Q3 net sales guided to $197.0B-$202.0B",
    "hasTranscript": True,
    "transcriptSummaryMd": "- Management described bookings as ahead of plan",
    "transcriptHighlights": [
        {"label": "Revenue", "value": "$200.6B (+20% YoY)"},
    ],
    "transcriptGeneratedAt": 1785990279,
    "sources": [
        {"title": "Second quarter results", "url": "https://www.example.com/q2"},
    ],
    "generatedAt": 1785980000,
    "source": "press_release",
}

FREE_QUARTER = {
    "fiscalPeriod": "Q2 2026",
    "reportDate": "2026-07-31",
    "headline": "Revenue grew 20% and operating income outpaced it",
    "kpiHighlights": [
        {"label": "Net Sales", "value": "$200.6B"},
        {"label": "Operating income", "value": "$27.5B"},
    ],
    "kpiHighlightCount": 6,
    "summaryTopics": ["Segment performance", "Margins"],
    "transcriptTopics": ["Demand", "Capital spending"],
    "hasTranscript": True,
    "hasGuidance": True,
    "guidanceDirection": "RAISED",
    "generatedAt": 1785980000,
    "source": "press_release",
}

REACTIONS_PAYLOAD = {
    "ticker": "NVDA",
    "asOf": "2026-08-21",
    "reactions": [
        {
            "reportDate": "2026-05-20",
            "timing": "AMC",
            "priorClose": 223.47,
            "nextClose": 219.51,
            "movePct": -1.77,
        },
        {
            "reportDate": "2026-02-25",
            "timing": None,
            "priorClose": 131.28,
            "nextClose": 120.15,
            "movePct": -8.48,
        },
    ],
}

STATISTICS_PAYLOAD = {
    "calculationVersion": "1.0.0",
    "asOf": 1234567890,
    "window": {
        "key": "2026-W01",
        "kind": "COMPLETED_WEEK",
        "startDate": "2025-12-29",
        "endDate": "2026-01-04",
    },
    "eventsInWindow": 120,
    "classifiedEvents": 118,
    "unclassifiedEvents": 2,
    "distinctTickers": 118,
    "completedReactions": 104,
    "pendingReactions": 14,
    "coverageRatio": 0.8814,
    "sufficientData": True,
    "beat": {
        "count": 80,
        "rate": 0.6780,
        "withReaction": 71,
        "fell": 30,
        "rose": 40,
        "flat": 1,
        "fellRate": 0.4225,
        "averageMovePct": 1.1,
    },
    "miss": {
        "count": 34,
        "rate": 0.2881,
        "withReaction": 30,
        "fell": 19,
        "rose": 11,
        "flat": 0,
        "fellRate": 0.6333,
        "averageMovePct": -2.2,
    },
    "inline": {
        "count": 4,
        "rate": 0.0339,
        "withReaction": 3,
        "fell": 2,
        "rose": 1,
        "flat": 0,
        "fellRate": 0.6667,
        "averageMovePct": -0.4,
    },
    "averageMovePct": 0.1,
    "baseline": {
        "window": {
            "key": "2026-W01-trailing52w",
            "kind": "TRAILING_BASELINE",
            "startDate": "2024-12-30",
            "endDate": "2025-12-28",
        },
        "classifiedEvents": 2400,
        "completedReactions": 2150,
        "distinctTickers": 900,
        "beatRate": 0.7300,
        "beatsFellRate": 0.4400,
        "coverageRatio": 0.8958,
        "sufficientData": True,
    },
    "deviation": {
        "beatRate": -0.0520,
        "beatsFellRate": -0.0175,
        "beatRateIsMaterial": False,
        "beatsFellRateIsMaterial": False,
    },
    "thresholds": {
        "minClassifiedEvents": 30,
        "minCoverageRatio": 0.80,
        "baselineWeeks": 52,
        "beatRateDeviation": 0.10,
        "reactionDivergence": 0.07,
    },
}

RANKED_PRO_PAYLOAD = {
    "asOf": 1789000000,
    "rankingVersion": "2026.08-v1",
    "reported": {
        "windowStart": "2026-08-26",
        "windowEnd": "2026-09-09",
        "totalInWindow": 87,
        "rows": [
            {
                "ticker": "NVDA",
                "reportDate": "2026-08-27",
                "fiscalPeriod": "Q2 FY2027",
                "headline": "Revenue and earnings exceeded the consensus estimate",
                "hasTranscriptSummary": True,
                "estimateEps": 1.01,
                "actualEps": 1.05,
                "surprisePct": 3.96,
                "outcome": "BEAT",
                "movePct": -6.38,
                "reactionPending": False,
                "awaitingConsensus": False,
                "marketCap": 4400000000000,
                "sentisenseScore7d": 12.4,
                "scoreChange7d": -3.1,
                "importance": 0.93,
            }
        ],
    },
    "upcoming": {
        "windowStart": "2026-09-09",
        "windowEnd": "2026-09-16",
        "totalInWindow": 41,
        "rows": [
            {
                "ticker": "ORCL",
                "companyName": "Oracle Corporation",
                "earningsDate": "2026-09-10",
                "earningsTime": "after_close",
                "confirmed": True,
                "estimatedEps": 1.48,
                "marketCap": 640000000000,
                "sentisenseScore7d": 4.2,
                "scoreChange7d": 1.0,
                "importance": 0.81,
            }
        ],
    },
}

RANKED_FREE_PAYLOAD = {
    **RANKED_PRO_PAYLOAD,
    "reported": {
        **RANKED_PRO_PAYLOAD["reported"],
        "rows": [
            RANKED_PRO_PAYLOAD["reported"]["rows"][0],
            {
                "ticker": "CRM",
                "reportDate": "2026-09-02",
                "outcome": "INLINE",
                "reactionPending": True,
                "importance": 0.86,
            },
            {
                "ticker": "AVGO",
                "reportDate": "2026-09-03",
                "outcome": "UNCLASSIFIED",
                "awaitingConsensus": True,
                "importance": 0.82,
            },
        ],
    },
    "upcoming": {
        **RANKED_PRO_PAYLOAD["upcoming"],
        "rows": [
            RANKED_PRO_PAYLOAD["upcoming"]["rows"][0],
            {
                "ticker": "ADBE",
                "companyName": "Adobe Inc.",
                "earningsDate": "2026-09-11",
                "earningsTime": "after_close",
                "confirmed": True,
                "importance": 0.76,
            },
            {
                "ticker": "KR",
                "companyName": "The Kroger Co.",
                "earningsDate": "2026-09-12",
                "earningsTime": "before_open",
                "confirmed": False,
                "importance": 0.68,
            },
        ],
    },
}


class TestGetEarningsSummaries:
    @patch.object(SentiSenseClient, "_get")
    def test_hits_the_ticker_path_and_upcases(self, mock_get, client):
        mock_get.return_value = _mock_response({"isPreview": False, "data": []})
        client.get_earnings_summaries("aapl")
        mock_get.assert_called_once_with(
            "/api/v1/stocks/AAPL/earnings-summaries", params={}
        )

    @patch.object(SentiSenseClient, "_get")
    def test_limit_is_sent_only_when_supplied(self, mock_get, client):
        mock_get.return_value = _mock_response({"isPreview": False, "data": []})
        client.get_earnings_summaries("AAPL", limit=4)
        mock_get.assert_called_once_with(
            "/api/v1/stocks/AAPL/earnings-summaries", params={"limit": 4}
        )

    @patch.object(SentiSenseClient, "_get")
    def test_parses_a_pro_quarter_in_full(self, mock_get, client):
        mock_get.return_value = _mock_response(
            {"isPreview": False, "previewReason": None, "data": [PRO_QUARTER]}
        )
        result = client.get_earnings_summaries("AMZN")

        assert result.is_preview is False
        assert len(result) == 1
        quarter = result.data[0]
        assert isinstance(quarter, EarningsQuarter)
        assert quarter.fiscalPeriod == "Q2 2026"
        assert quarter.reportDate == "2026-07-31"
        assert quarter.summaryMd.startswith("- Revenue was")
        assert quarter.guidance.startswith("Q3 net sales")
        assert quarter.source == "press_release"
        assert quarter.generatedAt == 1785980000

    @patch.object(SentiSenseClient, "_get")
    def test_kpi_cards_and_sources_are_typed(self, mock_get, client):
        mock_get.return_value = _mock_response({"isPreview": False, "data": [PRO_QUARTER]})
        quarter = client.get_earnings_summaries("AMZN").data[0]

        assert all(isinstance(k, EarningsKpiHighlight) for k in quarter.kpiHighlights)
        assert [k.label for k in quarter.kpiHighlights] == ["Net Sales", "Operating income"]
        assert quarter.kpiHighlights[0].yoy == "+20% YoY"
        assert all(isinstance(s, EarningsSource) for s in quarter.sources)
        assert quarter.sources[0].url == "https://www.example.com/q2"

    @patch.object(SentiSenseClient, "_get")
    def test_call_summary_fields_travel_together(self, mock_get, client):
        mock_get.return_value = _mock_response({"isPreview": False, "data": [PRO_QUARTER]})
        quarter = client.get_earnings_summaries("AMZN").data[0]

        assert quarter.hasTranscript is True
        assert quarter.transcriptGeneratedAt == 1785990279
        assert quarter.transcriptHighlights[0].label == "Revenue"
        # A call highlight need not carry a year-over-year figure.
        assert quarter.transcriptHighlights[0].yoy is None

    @patch.object(SentiSenseClient, "_get")
    def test_quarter_without_a_call_says_so_rather_than_omitting_it(self, mock_get, client):
        payload = {k: v for k, v in PRO_QUARTER.items() if not k.startswith("transcript")}
        payload["hasTranscript"] = False
        mock_get.return_value = _mock_response({"isPreview": False, "data": [payload]})
        quarter = client.get_earnings_summaries("AAPL").data[0]

        assert quarter.hasTranscript is False
        assert quarter.transcriptSummaryMd is None
        assert quarter.transcriptHighlights == []
        assert quarter.transcriptGeneratedAt is None

    @patch.object(SentiSenseClient, "_get")
    def test_parses_the_free_preview_shape(self, mock_get, client):
        mock_get.return_value = _mock_response(
            {
                "isPreview": True,
                "previewReason": "PRO_REQUIRED",
                "totalCount": 8,
                "data": [FREE_QUARTER],
            }
        )
        result = client.get_earnings_summaries("AMZN")

        assert result.is_preview is True
        assert result.preview_reason == "PRO_REQUIRED"
        assert result.total_count == 8

        quarter = result.data[0]
        assert quarter.headline.startswith("Revenue grew")
        assert quarter.kpiHighlightCount == 6
        assert quarter.summaryTopics == ["Segment performance", "Margins"]
        assert quarter.transcriptTopics == ["Demand", "Capital spending"]
        assert quarter.hasGuidance is True
        assert quarter.guidanceDirection == "RAISED"
        # The preview never carries a body, a KPI history, or a guidance figure.
        assert quarter.summaryMd is None
        assert quarter.transcriptSummaryMd is None
        assert quarter.guidance is None
        assert [k.yoy for k in quarter.kpiHighlights] == [None, None]

    @patch.object(SentiSenseClient, "_get")
    def test_uncovered_ticker_is_an_empty_list_not_an_error(self, mock_get, client):
        mock_get.return_value = _mock_response(
            {"isPreview": False, "previewReason": None, "data": []}
        )
        result = client.get_earnings_summaries("AAPL")
        assert result.data == []
        assert len(result) == 0


class TestGetRecentEarnings:
    @patch.object(SentiSenseClient, "_get")
    def test_sends_no_window_arguments_by_default(self, mock_get, client):
        mock_get.return_value = _mock_response({"isPreview": False, "data": []})
        client.get_recent_earnings()
        mock_get.assert_called_once_with("/api/v1/earnings/recent", params={})

    @patch.object(SentiSenseClient, "_get")
    def test_passes_days_and_limit_through(self, mock_get, client):
        mock_get.return_value = _mock_response({"isPreview": False, "data": []})
        client.get_recent_earnings(days=14, limit=25)
        mock_get.assert_called_once_with(
            "/api/v1/earnings/recent", params={"days": 14, "limit": 25}
        )

    @patch.object(SentiSenseClient, "_get")
    def test_parses_rows_newest_first(self, mock_get, client):
        mock_get.return_value = _mock_response(
            {
                "isPreview": False,
                "previewReason": None,
                "data": [
                    {
                        "ticker": "MCHP",
                        "fiscalPeriod": "Q1 FY2027",
                        "reportDate": "2026-08-06",
                        "headline": "Net sales rose 38% year over year",
                        "hasTranscriptSummary": False,
                        "generatedAt": 1786077821,
                    },
                    {
                        "ticker": "AMZN",
                        "fiscalPeriod": "Q2 2026",
                        "reportDate": "2026-07-31",
                        "headline": "Revenue grew 20%",
                        "hasTranscriptSummary": True,
                        "generatedAt": 1785990279,
                    },
                ],
            }
        )
        result = client.get_recent_earnings(days=7)

        assert result.is_preview is False
        assert [r.ticker for r in result] == ["MCHP", "AMZN"]
        assert all(isinstance(r, RecentEarningsEntry) for r in result)
        assert result.data[0].reportDate == "2026-08-06"
        assert result.data[0].hasTranscriptSummary is False
        assert result.data[1].hasTranscriptSummary is True

    @patch.object(SentiSenseClient, "_get")
    def test_quiet_window_is_an_empty_list_not_an_error(self, mock_get, client):
        mock_get.return_value = _mock_response({"isPreview": False, "data": []})
        assert client.get_recent_earnings(days=1).data == []


class TestGetEarningsReactions:
    @patch.object(SentiSenseClient, "_get")
    def test_hits_the_direct_ticker_path_and_parses_rows(self, mock_get, client):
        mock_get.return_value = _mock_response(REACTIONS_PAYLOAD)

        result = client.get_earnings_reactions("nvda")

        mock_get.assert_called_once_with(
            "/api/v1/stocks/NVDA/earnings/reactions", params={}
        )
        assert isinstance(result, EarningsReactions)
        assert all(isinstance(row, EarningsReaction) for row in result.reactions)
        assert result.reactions[0].movePct == -1.77
        assert "timing" in result.reactions[1]
        assert result.reactions[1].timing is None


class TestGetEarningsStatistics:
    @patch.object(SentiSenseClient, "_get")
    def test_passes_the_window_and_parses_every_nested_block(self, mock_get, client):
        mock_get.return_value = _mock_response(
            {"isPreview": False, "previewReason": None, "data": STATISTICS_PAYLOAD}
        )

        result = client.get_earnings_statistics(window="last_completed_week")

        mock_get.assert_called_once_with(
            "/api/v1/earnings/statistics",
            params={"window": "last_completed_week"},
        )
        assert result.is_preview is False
        assert isinstance(result.data, EarningsStatistics)
        assert result.window.key == "2026-W01"
        assert isinstance(result.beat, EarningsOutcomeStatistics)
        assert result.beat.fellRate == 0.4225
        assert isinstance(result.baseline, EarningsStatisticsBaseline)
        assert result.baseline.window.kind == "TRAILING_BASELINE"
        assert result.deviation.beatRate == -0.052
        assert result.thresholds.minClassifiedEvents == 30


class TestGetRankedEarnings:
    @patch.object(SentiSenseClient, "_get")
    def test_sends_no_query_arguments_by_default(self, mock_get, client):
        mock_get.return_value = _mock_response(
            {"isPreview": False, "data": RANKED_PRO_PAYLOAD}
        )
        client.get_ranked_earnings()
        mock_get.assert_called_once_with("/api/v1/earnings/ranked", params={})

    @patch.object(SentiSenseClient, "_get")
    def test_passes_all_ranking_windows_and_limits(self, mock_get, client):
        mock_get.return_value = _mock_response(
            {"isPreview": False, "data": RANKED_PRO_PAYLOAD}
        )
        client.get_ranked_earnings(
            reported_days=10,
            reported_limit=20,
            upcoming_days=5,
            upcoming_limit=15,
        )
        mock_get.assert_called_once_with(
            "/api/v1/earnings/ranked",
            params={
                "reportedDays": 10,
                "reportedLimit": 20,
                "upcomingDays": 5,
                "upcomingLimit": 15,
            },
        )

    @patch.object(SentiSenseClient, "_get")
    def test_parses_the_full_ranking(self, mock_get, client):
        mock_get.return_value = _mock_response(
            {"isPreview": False, "previewReason": None, "data": RANKED_PRO_PAYLOAD}
        )

        result = client.get_ranked_earnings()

        assert isinstance(result.data, RankedEarnings)
        assert result.rankingVersion == "2026.08-v1"
        assert result.reported.totalInWindow == 87
        assert isinstance(result.reported.rows[0], RankedReportedEarnings)
        assert result.reported.rows[0].surprisePct == 3.96
        assert isinstance(result.upcoming.rows[0], RankedUpcomingEarnings)
        assert result.upcoming.rows[0].earningsTime == "after_close"

    @patch.object(SentiSenseClient, "_get")
    def test_parses_the_free_preview_and_omitted_optional_fields(self, mock_get, client):
        mock_get.return_value = _mock_response(
            {
                "isPreview": True,
                "previewReason": "PRO_REQUIRED",
                "data": RANKED_FREE_PAYLOAD,
            }
        )

        result = client.get_ranked_earnings()

        assert result.is_preview is True
        assert result.preview_reason == "PRO_REQUIRED"
        assert result.reported.totalInWindow == 87
        assert result.upcoming.totalInWindow == 41
        assert len(result.reported.rows) == 3
        assert len(result.upcoming.rows) == 3
        assert result.reported.rows[1].estimateEps is None
        assert result.upcoming.rows[1].estimatedEps is None
