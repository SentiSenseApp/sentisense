"""Unit tests for the earnings analysis report and the recent-reporters feed.

Two contracts are worth gating here. First, the quarter arrives in two shapes on
the same envelope: a PRO quarter carries the bodies (``summaryMd``, guidance,
call summary), a FREE quarter replaces them with section titles and a guidance
direction. A client that reads ``summaryMd`` without checking ``is_preview``
silently renders an empty panel for every free key, so both shapes are parsed
here from realistic payloads.

Second, absence is explicit rather than implied. ``hasTranscript`` is ``False``
on a quarter with no call summary instead of the field being dropped, and the
optional ``yoy`` on a KPI card is ``None`` rather than an empty string. Coercing
either loses information the API deliberately sends.
"""

from unittest.mock import MagicMock, patch

import pytest

from sentisense import SentiSenseClient
from sentisense.types import (
    EarningsKpiHighlight,
    EarningsQuarter,
    EarningsSource,
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
