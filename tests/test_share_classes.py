"""Share classes and the listing a per-share figure is quoted for.

A company with more than one separately listed share class lists them in
``shareClasses`` on its profile and on its primary class's row of the detailed
stock list. Estimates and earnings summaries are stored under the primary class,
so a request for ``BRK-A`` answers with ``BRK.B`` figures and names that listing
in ``ticker``. Reading a ``BRK.B`` per-share figure against a ``BRK.A`` price is
off by a factor of 1,500, which is why the field has to survive parsing.

Fixtures are trimmed live responses. Every field is optional on the wire, so the
payloads without it (single-class companies, older servers) must still parse.
"""

import json
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from sentisense import (
    AnalystEstimates,
    EarningsQuarter,
    EarningsSummariesResult,
    PreviewResult,
    SentiSenseClient,
    ShareClass,
    StockDetail,
)

PAYLOADS = json.loads(
    (Path(__file__).parent / "fixtures" / "share_classes_live.json").read_text()
)


def call_with_payload(method, payload, *args, **kwargs):
    client = SentiSenseClient("test-api-key")
    response = MagicMock(status_code=200, ok=True)
    response.json.return_value = payload
    with patch.object(client.session, "get", return_value=response):
        return getattr(client, method)(*args, **kwargs)


class TestProfileShareClasses:
    @pytest.mark.parametrize(
        "fixture,expected",
        [
            ("profileBrkA", [("BRK.B", True), ("BRK.A", False)]),
            ("profileGoog", [("GOOGL", True), ("GOOG", False)]),
        ],
    )
    def test_lists_every_class_primary_first(self, fixture, expected):
        profile = call_with_payload("get_stock_profile", PAYLOADS[fixture], "X")
        classes = profile["shareClasses"]
        assert [(c["ticker"], c["primary"]) for c in classes] == expected
        typed = [ShareClass.from_dict(c) for c in classes]
        assert typed[0].primary is True
        assert profile["ticker"] in [c.ticker for c in typed]

    def test_single_class_company_has_no_field(self):
        profile = call_with_payload("get_stock_profile", PAYLOADS["profileAapl"], "AAPL")
        assert "shareClasses" not in profile


class TestDetailedRowShareClasses:
    def test_primary_row_carries_typed_classes(self):
        rows = call_with_payload("get_all_stocks_detailed", PAYLOADS["detailedRows"])
        by_ticker = {r.ticker: r for r in rows}
        brk = by_ticker["BRK.B"]
        assert isinstance(brk, StockDetail)
        assert all(isinstance(c, ShareClass) for c in brk.shareClasses)
        assert [(c.ticker, c.primary) for c in brk.shareClasses] == [
            ("BRK.B", True),
            ("BRK.A", False),
        ]
        # Dict-style access keeps working on the typed entries.
        assert by_ticker["GOOGL"].shareClasses[1]["ticker"] == "GOOG"
        # The secondary classes have no row of their own.
        assert "BRK.A" not in by_ticker and "GOOG" not in by_ticker

    def test_single_class_row_is_none(self):
        rows = call_with_payload("get_all_stocks_detailed", PAYLOADS["detailedRows"])
        aapl = next(r for r in rows if r.ticker == "AAPL")
        assert aapl.shareClasses is None
        assert aapl.name == "Apple"

    def test_from_dict_accepts_already_typed_entries(self):
        detail = StockDetail(ticker="ZG", shareClasses=[ShareClass("ZG", True)])
        assert detail.shareClasses == [ShareClass(ticker="ZG", primary=True)]


class TestEstimatesTicker:
    def test_brk_a_answers_brk_b(self):
        result = call_with_payload(
            "get_analyst_estimates", PAYLOADS["estimatesBrkA"], "BRK-A"
        )
        assert isinstance(result, PreviewResult)
        data = cast(AnalystEstimates, result.data)
        assert data["ticker"] == "BRK.B"
        assert result.ticker == "BRK.B"
        assert result["ticker"] == "BRK.B"
        assert result.data["estimates"][0]["periodType"] == "CURRENT_QUARTER"

    def test_older_payload_without_ticker_still_parses(self):
        result = call_with_payload(
            "get_analyst_estimates", PAYLOADS["estimatesLegacy"], "BRK-A"
        )
        assert result.data.get("ticker") is None
        assert result.data["surprises"][0]["surprisePct"] == 17.35


class TestEarningsSummariesTicker:
    def test_brk_a_answers_brk_b_on_an_empty_list(self):
        payload = PAYLOADS["earningsSummariesBrkA"]
        result = call_with_payload("get_earnings_summaries", payload, "BRK-A", limit=1)
        assert isinstance(result, EarningsSummariesResult)
        assert isinstance(result, PreviewResult)
        assert result.ticker == "BRK.B"
        assert result.data == []
        assert list(result) == []
        assert len(result) == 0
        assert not result
        assert result.is_preview is False
        assert result.total_count == 0

    def test_goog_answers_googl_and_list_behavior_is_unchanged(self):
        payload = PAYLOADS["earningsSummariesGoog"]
        result = call_with_payload("get_earnings_summaries", payload, "GOOG", limit=1)
        assert result.ticker == "GOOGL"
        assert len(result) == 1
        assert isinstance(result[0], EarningsQuarter)
        assert [q.fiscalPeriod for q in result] == [payload["data"][0]["fiscalPeriod"]]
        assert result.data[0] is result[0]
        assert result.total_count == payload["totalCount"]
        assert result.preview_reason is None
        assert result.upgrade is None

    def test_preview_envelope_keeps_ticker_and_metadata(self):
        quarter = dict(PAYLOADS["earningsSummariesGoog"]["data"][0])
        payload = {
            "isPreview": True,
            "previewReason": "PRO_REQUIRED",
            "totalCount": 8,
            "upgrade": {"plan": "PRO", "message": "Upgrade", "url": "https://sentisense.ai/pricing"},
            "data": [quarter],
            "ticker": "GOOGL",
        }
        result = call_with_payload("get_earnings_summaries", payload, "GOOG")
        assert result.ticker == "GOOGL"
        assert result.is_preview is True
        assert result.preview_reason == "PRO_REQUIRED"
        assert result.total_count == 8
        assert result.upgrade["plan"] == "PRO"

    def test_older_payload_without_ticker_reads_none(self):
        payload = PAYLOADS["earningsSummariesLegacy"]
        assert "ticker" not in payload
        result = call_with_payload("get_earnings_summaries", payload, "GOOG")
        assert result.ticker is None
        assert len(result) == 1
        assert result.total_count == payload["totalCount"]
