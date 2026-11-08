"""Unit tests for ``get_institution_history`` and the institution detail paging arguments."""

import dataclasses
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from sentisense import (
    InstitutionDetail,
    InstitutionHistory,
    InstitutionHistoryQuarter,
    InstitutionHolding,
    InstitutionPositionPoint,
    InstitutionScope,
    SentiSenseClient,
)

HISTORY_PATH = "/api/v1/institutional/institution/Renaissance-Technologies/history"
DETAIL_PATH = "/api/v1/institutional/institution/Berkshire-Hathaway"

AVAILABLE_ROW = {
    "reportDate": "2026-06-30", "value": "2026Q2", "label": "Q2 2026", "status": "settled",
    "comparisonStatus": "AVAILABLE", "comparisonReportDate": "2026-03-31",
    "totalValueUsd": 72000000000, "positionsHeld": 3100, "top10Pct": 12.0,
    "newPositions": 550, "increasedPositions": 1080, "decreasedPositions": 1500,
    "soldOutPositions": 620, "boughtUsd": 22000000000, "trimmedUsd": 18000000000,
    "exitedUsd": 5500000000, "netFlowUsd": -1500000000, "priceEffectUsd": 9600000000,
}
# The oldest filing has nothing to compare with, so the flow fields are omitted.
NO_COMPARISON_ROW = {
    "reportDate": "2025-06-30", "value": "2025Q2", "label": "Q2 2025", "status": "settled",
    "comparisonStatus": "PRIOR_QUARTER_UNAVAILABLE",
    "totalValueUsd": 60000000000, "positionsHeld": 2900, "top10Pct": 11.5,
}
HISTORY = {
    "isPreview": False,
    "previewReason": None,
    "data": {
        "filerCik": "0001037389",
        "urlSlug": "Renaissance-Technologies",
        "displayName": "Renaissance Technologies",
        "quarters": [AVAILABLE_ROW, NO_COMPARISON_ROW],
        "positions": {
            "NVDA": [
                {"reportDate": "2026-06-30", "shares": 7000000, "valueUsd": 1400000000},
                {"reportDate": "2026-03-31", "shares": 2500000, "valueUsd": 450000000},
            ],
            "META": [],
        },
    },
}
HISTORY_FREE = {
    "isPreview": True,
    "previewReason": "PRO_REQUIRED",
    "totalCount": 12,
    "upgrade": {"plan": "PRO"},
    "data": {
        "filerCik": "0001037389",
        "urlSlug": "Renaissance-Technologies",
        "displayName": "Renaissance Technologies",
        "quarters": [AVAILABLE_ROW],
    },
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


class TestHistoryRequest:
    @patch.object(SentiSenseClient, "_get")
    def test_path_and_no_params_by_default(self, mock_get, client):
        mock_get.return_value = _mock_response(HISTORY)
        client.get_institution_history("Renaissance-Technologies")
        mock_get.assert_called_once_with(HISTORY_PATH, params={})

    @patch.object(SentiSenseClient, "_get")
    def test_quarters_and_tickers_list_is_comma_joined(self, mock_get, client):
        mock_get.return_value = _mock_response(HISTORY)
        client.get_institution_history("Renaissance-Technologies", quarters=8, tickers=["NVDA", "META"])
        mock_get.assert_called_once_with(HISTORY_PATH, params={"quarters": 8, "tickers": "NVDA,META"})

    @patch.object(SentiSenseClient, "_get")
    def test_tickers_string_is_sent_as_given(self, mock_get, client):
        mock_get.return_value = _mock_response(HISTORY)
        client.get_institution_history("Renaissance-Technologies", tickers="NVDA,META")
        mock_get.assert_called_once_with(HISTORY_PATH, params={"tickers": "NVDA,META"})

    @patch.object(SentiSenseClient, "_get")
    def test_positional_quarters(self, mock_get, client):
        mock_get.return_value = _mock_response(HISTORY)
        client.get_institution_history("1037389", 4)
        mock_get.assert_called_once_with(
            "/api/v1/institutional/institution/1037389/history", params={"quarters": 4}
        )

    @patch.object(SentiSenseClient, "_get")
    def test_empty_ticker_list_is_omitted(self, mock_get, client):
        mock_get.return_value = _mock_response(HISTORY)
        client.get_institution_history("Renaissance-Technologies", tickers=[])
        mock_get.assert_called_once_with(HISTORY_PATH, params={})

    def test_the_http_request_carries_the_joined_tickers(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(HISTORY)) as get:
            client.get_institution_history("Renaissance-Technologies", quarters=8, tickers=("NVDA", "META"))
        args, kwargs = get.call_args
        assert args[0].endswith(HISTORY_PATH)
        assert kwargs["params"] == {"quarters": 8, "tickers": "NVDA,META"}


class TestHistoryParsing:
    @patch.object(SentiSenseClient, "_get")
    def test_unwraps_into_typed_rows_and_positions(self, mock_get, client):
        mock_get.return_value = _mock_response(HISTORY)
        result = client.get_institution_history("Renaissance-Technologies", tickers=["NVDA", "META"])

        assert result.is_preview is False
        assert isinstance(result.data, InstitutionHistory)
        assert result.urlSlug == "Renaissance-Technologies"
        assert all(isinstance(q, InstitutionHistoryQuarter) for q in result.quarters)
        newest = result.quarters[0]
        assert newest.netFlowUsd == newest.boughtUsd - newest.trimmedUsd - newest.exitedUsd
        assert result.positions["NVDA"][0] == InstitutionPositionPoint("2026-06-30", 7000000, 1400000000)
        assert result.positions["META"] == []

    @patch.object(SentiSenseClient, "_get")
    def test_every_wire_field_is_typed(self, mock_get, client):
        mock_get.return_value = _mock_response(HISTORY)
        row = client.get_institution_history("Renaissance-Technologies").quarters[0]
        declared = {f.name for f in dataclasses.fields(InstitutionHistoryQuarter)}
        assert set(AVAILABLE_ROW) <= declared, set(AVAILABLE_ROW) - declared
        for key, value in AVAILABLE_ROW.items():
            assert getattr(row, key) == value

    @patch.object(SentiSenseClient, "_get")
    def test_omitted_comparison_fields_read_as_none_never_zero(self, mock_get, client):
        mock_get.return_value = _mock_response(HISTORY)
        oldest = client.get_institution_history("Renaissance-Technologies").quarters[1]
        assert oldest.comparisonStatus == "PRIOR_QUARTER_UNAVAILABLE"
        assert oldest.comparisonReportDate is None
        for name in (
            "newPositions", "increasedPositions", "decreasedPositions", "soldOutPositions",
            "boughtUsd", "trimmedUsd", "exitedUsd", "netFlowUsd", "priceEffectUsd",
        ):
            assert getattr(oldest, name) is None, name
        assert oldest.totalValueUsd == 60000000000

    @patch.object(SentiSenseClient, "_get")
    def test_positions_absent_without_tickers(self, mock_get, client):
        mock_get.return_value = _mock_response(HISTORY_FREE)
        result = client.get_institution_history("Renaissance-Technologies")
        assert result.positions is None

    @patch.object(SentiSenseClient, "_get")
    def test_free_preview_carries_the_window_size(self, mock_get, client):
        mock_get.return_value = _mock_response(HISTORY_FREE)
        result = client.get_institution_history("Renaissance-Technologies", quarters=12)
        assert result.is_preview is True
        assert result.preview_reason == "PRO_REQUIRED"
        assert result.total_count == 12
        assert len(result.quarters) == 1

    def test_the_wrapper_has_no_field_named_data(self):
        assert "data" not in {f.name for f in dataclasses.fields(InstitutionHistory)}

    def test_from_dict_ignores_unknown_keys(self):
        history = InstitutionHistory.from_dict(
            {"filerCik": "1", "quarters": [dict(AVAILABLE_ROW, extra=True)], "extra": 1}
        )
        assert history.quarters[0].label == "Q2 2026"


DETAIL_PAGE = {
    "isPreview": False,
    "previewReason": None,
    "totalCount": 40,
    "data": {
        "filerCik": "1067983",
        "displayName": "Berkshire Hathaway",
        "totalValueUsd": 300000000000,
        "holdingsCount": 41,
        "positionsHeld": 40,
        "comparisonStatus": "AVAILABLE",
        "comparisonReportDate": "2026-03-31",
        "priorTotalValueUsd": 280000000000,
        "priorPositionsHeld": 38,
        "holdings": [
            {
                "ticker": "AAPL", "companyName": "Apple Inc.", "shares": 100, "valueUsd": 400000,
                "changeType": "INCREASED", "sharesChange": 10, "sharesChangePct": 11.1,
                "portfolioWeight": 40.0, "priorValueUsd": 330000, "priorPortfolioWeight": 35.0,
                "estimatedFlowUsd": 40000,
            }
        ],
        "returnedCount": 1,
        "offset": 0,
        "scope": {"count": 5, "valueUsd": 900000, "priorValueUsd": 700000, "estimatedFlowUsd": 90000},
    },
}
DETAIL_OLD = {
    "isPreview": False,
    "previewReason": None,
    "data": {
        "filerCik": "1067983",
        "holdings": [{"ticker": "AAPL", "shares": 100, "valueUsd": 400000, "portfolioWeight": 40.0}],
    },
}


class TestDetailRequest:
    @patch.object(SentiSenseClient, "_get")
    def test_existing_call_sends_no_params(self, mock_get, client):
        mock_get.return_value = _mock_response(DETAIL_OLD)
        client.get_institution_detail("Berkshire-Hathaway")
        mock_get.assert_called_once_with(DETAIL_PATH)

    @patch.object(SentiSenseClient, "_get")
    def test_every_new_argument_maps_to_its_wire_name(self, mock_get, client):
        mock_get.return_value = _mock_response(DETAIL_PAGE)
        client.get_institution_detail(
            "Berkshire-Hathaway",
            limit=25,
            offset=50,
            sort_by="estimatedFlowUsd",
            sort_dir="asc",
            change_type=["NEW", "INCREASED"],
            q="app",
            min_weight=1.5,
        )
        mock_get.assert_called_once_with(
            DETAIL_PATH,
            params={
                "limit": 25, "offset": 50, "sortBy": "estimatedFlowUsd", "sortDir": "asc",
                "changeType": "NEW,INCREASED", "q": "app", "minWeight": 1.5,
            },
        )

    @patch.object(SentiSenseClient, "_get")
    def test_change_type_string_is_sent_as_given_and_only_given_params_are_sent(self, mock_get, client):
        mock_get.return_value = _mock_response(DETAIL_PAGE)
        client.get_institution_detail("Berkshire-Hathaway", limit=10, change_type="SOLD_OUT")
        mock_get.assert_called_once_with(DETAIL_PATH, params={"limit": 10, "changeType": "SOLD_OUT"})

    @patch.object(SentiSenseClient, "_get")
    def test_zero_values_are_still_sent(self, mock_get, client):
        mock_get.return_value = _mock_response(DETAIL_PAGE)
        client.get_institution_detail("Berkshire-Hathaway", limit=5, offset=0, min_weight=0)
        mock_get.assert_called_once_with(
            DETAIL_PATH, params={"limit": 5, "offset": 0, "minWeight": 0}
        )


class TestDetailParsing:
    @patch.object(SentiSenseClient, "_get")
    def test_new_fields_arrive_untouched(self, mock_get, client):
        mock_get.return_value = _mock_response(DETAIL_PAGE)
        result = client.get_institution_detail("Berkshire-Hathaway", limit=1)
        detail = cast(InstitutionDetail, result.data)
        assert isinstance(detail, dict)
        assert detail["priorTotalValueUsd"] == 280000000000
        assert detail["priorPositionsHeld"] == 38
        scope = cast(InstitutionScope, detail["scope"])
        assert scope["estimatedFlowUsd"] == 90000
        holding = cast(InstitutionHolding, detail["holdings"][0])
        assert holding["priorValueUsd"] == 330000
        assert holding["priorPortfolioWeight"] == 35.0
        assert holding["estimatedFlowUsd"] == 40000
        assert result.total_count == 40

    @patch.object(SentiSenseClient, "_get")
    def test_a_response_without_the_new_fields_still_parses(self, mock_get, client):
        mock_get.return_value = _mock_response(DETAIL_OLD)
        detail = client.get_institution_detail("Berkshire-Hathaway").data
        for key in ("priorTotalValueUsd", "priorPositionsHeld", "scope"):
            assert key not in detail
        holding = detail["holdings"][0]
        for key in ("priorValueUsd", "priorPortfolioWeight", "estimatedFlowUsd"):
            assert key not in holding
        assert holding["valueUsd"] == 400000

    def test_annotations_have_no_required_keys(self):
        assert InstitutionHolding.__total__ is False
        assert InstitutionScope.__total__ is False
        assert InstitutionHolding() == {}
        assert InstitutionScope() == {}
        for name in ("priorTotalValueUsd", "priorPositionsHeld", "scope"):
            assert name in InstitutionDetail.__annotations__
        for name in ("priorValueUsd", "priorPortfolioWeight", "estimatedFlowUsd"):
            assert name in InstitutionHolding.__annotations__
