"""Unit tests for ``get_stock_holders_history``.

Three contracts are gated here because each one fails quietly rather than loudly:

* The newest quarter can still be filing. Its counts cover only the institutions
  that have filed so far, so a caller that reads ``quarters[0]`` as "the latest
  ownership" without checking ``status`` quotes a partial quarter as a whole one.
* ``sharesOutstanding``, ``institutionalOwnershipPct``, ``avgClosePrice`` and
  ``dollarFlowUsd`` are omitted from the JSON when they cannot be computed (an ADR,
  an unpriced quarter). They must read as ``None``, never as zero: a zero ownership
  percentage or a zero dollar flow is a claim, not an absence.
* A free key gets the newest four quarters with ``total_count`` naming the full
  window; the envelope is unwrapped into a typed payload either way.
"""

import dataclasses
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sentisense import HoldersHistory, HoldersHistoryQuarter, SentiSenseClient

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# A live free-key response for one stock: the newest quarter still filing, three settled.
FREE_PREVIEW = json.loads((FIXTURES / "holders_history_live.json").read_text())

# Real quarter rows with the optional fields omitted by the server.
ADR_ROW = {  # no per-class shares outstanding, so no ownership percentage
    "reportDate": "2026-06-30", "value": "2026Q2", "label": "Q2 2026", "status": "settled",
    "pending": False, "holderCount": 3546, "totalInstitutionalShares": 761442577,
    "totalInstitutionalValue": 360916323290, "netSharesChange": -1535802,
    "totalSharesBought": 62482363, "totalSharesSold": 64018165, "newPositions": 469,
    "increasedPositions": 1432, "decreasedPositions": 1288, "soldOutPositions": 2,
    "avgClosePrice": 405.7901612903225, "dollarFlowUsd": -623213341.2899998,
}
UNPRICED_ROW = {  # no quarterly average price, so no dollar flow
    "reportDate": "2026-06-30", "value": "2026Q2", "label": "Q2 2026", "status": "settled",
    "pending": False, "holderCount": 4895, "totalInstitutionalShares": 914790286,
    "totalInstitutionalValue": 457136783995, "sharesOutstanding": 1408035161,
    "institutionalOwnershipPct": 64.97, "netSharesChange": 15598823,
    "totalSharesBought": 44629268, "totalSharesSold": 29030445, "newPositions": 255,
    "increasedPositions": 1987, "decreasedPositions": 1983, "soldOutPositions": 2,
}


@pytest.fixture
def client():
    return SentiSenseClient("test-api-key")


def _mock_response(json_data):
    resp = MagicMock()
    resp.status_code = 200
    resp.ok = True
    resp.json.return_value = json_data
    return resp


class TestRequest:
    @patch.object(SentiSenseClient, "_get")
    def test_path_and_no_params_by_default(self, mock_get, client):
        mock_get.return_value = _mock_response(FREE_PREVIEW)
        client.get_stock_holders_history("CRM")
        mock_get.assert_called_once_with("/api/v1/institutional/holders/CRM/history", params={})

    @patch.object(SentiSenseClient, "_get")
    def test_quarters_is_sent_when_given(self, mock_get, client):
        mock_get.return_value = _mock_response(FREE_PREVIEW)
        client.get_stock_holders_history("CRM", quarters=20)
        mock_get.assert_called_once_with(
            "/api/v1/institutional/holders/CRM/history", params={"quarters": 20}
        )

    @patch.object(SentiSenseClient, "_get")
    def test_quarters_keyword_or_positional(self, mock_get, client):
        mock_get.return_value = _mock_response(FREE_PREVIEW)
        client.get_stock_holders_history("CRM", 8)
        mock_get.assert_called_once_with(
            "/api/v1/institutional/holders/CRM/history", params={"quarters": 8}
        )


class TestFreePreview:
    @patch.object(SentiSenseClient, "_get")
    def test_unwraps_into_typed_quarters(self, mock_get, client):
        mock_get.return_value = _mock_response(FREE_PREVIEW)
        result = client.get_stock_holders_history("CRM")

        assert result.is_preview is True
        assert result.preview_reason == "PRO_REQUIRED"
        assert result.total_count == 12
        assert result.upgrade["plan"] == "PRO"
        assert isinstance(result.data, HoldersHistory)
        assert result.ticker == "CRM"
        assert len(result.quarters) == 4
        assert all(isinstance(q, HoldersHistoryQuarter) for q in result.quarters)

    @patch.object(SentiSenseClient, "_get")
    def test_newest_first_and_the_filing_quarter_is_labeled(self, mock_get, client):
        mock_get.return_value = _mock_response(FREE_PREVIEW)
        quarters = client.get_stock_holders_history("CRM").quarters

        dates = [q.reportDate for q in quarters]
        assert dates == sorted(dates, reverse=True)
        newest = quarters[0]
        assert (newest.status, newest.pending) == ("filing", True)
        settled = next(q for q in quarters if q.status == "settled")
        assert settled.pending is False
        assert (settled.value, settled.label) == ("2026Q2", "Q2 2026")

    @patch.object(SentiSenseClient, "_get")
    def test_every_wire_field_is_typed(self, mock_get, client):
        """Every key the server sent lands on a declared field, none is dropped."""
        mock_get.return_value = _mock_response(FREE_PREVIEW)
        quarter = client.get_stock_holders_history("CRM").quarters[1]

        declared = {f.name for f in dataclasses.fields(HoldersHistoryQuarter)}
        wire = set(FREE_PREVIEW["data"]["quarters"][1])
        assert wire <= declared, wire - declared
        for key, value in FREE_PREVIEW["data"]["quarters"][1].items():
            assert getattr(quarter, key) == value

    @patch.object(SentiSenseClient, "_get")
    def test_flow_arithmetic_holds_on_the_live_rows(self, mock_get, client):
        mock_get.return_value = _mock_response(FREE_PREVIEW)
        for q in client.get_stock_holders_history("CRM").quarters:
            assert q.netSharesChange == q.totalSharesBought - q.totalSharesSold
            assert q.dollarFlowUsd == pytest.approx(q.netSharesChange * q.avgClosePrice)
            assert q.institutionalOwnershipPct == pytest.approx(
                100 * q.totalInstitutionalShares / q.sharesOutstanding, abs=0.005
            )


class TestAbsentFields:
    @patch.object(SentiSenseClient, "_get")
    def test_absent_shares_outstanding_reads_none_not_zero(self, mock_get, client):
        mock_get.return_value = _mock_response(
            {"isPreview": False, "previewReason": None,
             "data": {"ticker": "TSM", "quarters": [ADR_ROW]}}
        )
        (q,) = client.get_stock_holders_history("TSM").quarters
        assert q.sharesOutstanding is None
        assert q.institutionalOwnershipPct is None
        assert q.dollarFlowUsd == pytest.approx(-623213341.29)

    @patch.object(SentiSenseClient, "_get")
    def test_absent_price_reads_none_not_zero(self, mock_get, client):
        mock_get.return_value = _mock_response(
            {"isPreview": False, "previewReason": None,
             "data": {"ticker": "BRK.B", "quarters": [UNPRICED_ROW]}}
        )
        result = client.get_stock_holders_history("BRK.B")
        (q,) = result.quarters
        assert result.ticker == "BRK.B"
        assert q.avgClosePrice is None
        assert q.dollarFlowUsd is None
        assert q.institutionalOwnershipPct == 64.97


class TestFullResponse:
    @patch.object(SentiSenseClient, "_get")
    def test_full_response_has_no_total_count(self, mock_get, client):
        mock_get.return_value = _mock_response(
            {"isPreview": False, "previewReason": None, "data": FREE_PREVIEW["data"]}
        )
        result = client.get_stock_holders_history("CRM")
        assert result.is_preview is False
        assert result.total_count is None
        assert result.upgrade is None
        assert len(result.quarters) == 4

    @patch.object(SentiSenseClient, "_get")
    def test_uncovered_ticker_is_an_empty_list(self, mock_get, client):
        mock_get.return_value = _mock_response(
            {"isPreview": False, "previewReason": None,
             "data": {"ticker": "ZZZZ", "quarters": []}}
        )
        result = client.get_stock_holders_history("ZZZZ")
        assert result.quarters == []

    def test_unknown_keys_are_ignored(self):
        row = dict(UNPRICED_ROW, someFutureField=1)
        history = HoldersHistory.from_dict({"ticker": "BRK.B", "quarters": [row], "extra": True})
        assert history.quarters[0].holderCount == 4895
        assert not hasattr(history.quarters[0], "someFutureField")

    def test_payload_type_has_no_data_field(self):
        # PreviewResult.data would shadow a field of that name.
        assert "data" not in {f.name for f in dataclasses.fields(HoldersHistory)}
