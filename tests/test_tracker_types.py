"""Tracker listing filters, named row cells and the ``filter`` parameter."""

from unittest.mock import MagicMock, patch

import pytest

from sentisense import (
    APIError,
    SentiSenseClient,
    TrackerFilter,
    TrackerListing,
    TrackerSnapshot,
    TrackerTableRow,
)
from sentisense.client import _tracker_filter_param
from sentisense.exceptions import _raise_for_status
from sentisense.types import TrackerListResponse


def _mock_response(status_code=200, json_data=None, reason="OK"):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.reason = reason
    resp.json.return_value = json_data or {}
    return resp


LISTING = {
    "trackers": [
        {
            "trackerId": "institution-aum",
            "displayName": "Largest institutions",
            "category": "institutional",
            "description": "13F filers by AUM.",
            "viewType": "table",
            "accessTier": "free",
            "methodologyAnchor": "#institution-rankings",
            "refreshIntervalSeconds": 86400,
            "canonicalUrl": "/api/v1/trackers/institution-aum",
        },
        {
            "trackerId": "data-center-moratoriums",
            "displayName": "Data center moratoriums",
            "category": "policy",
            "description": "Pauses, limits and proposals.",
            "viewType": "table",
            "accessTier": "free",
            "methodologyAnchor": "#data-center-moratoriums",
            "refreshIntervalSeconds": 86400,
            "canonicalUrl": "/api/v1/trackers/data-center-moratoriums",
            "filters": [
                {"key": "category", "values": ["federal", "state", "local", "governor", "company-filing"]},
                {"key": "state", "values": ["AZ", "FEDERAL", "TX"]},
            ],
        },
    ]
}

FILING_ROW = {
    "rank": 13,
    "rowId": "company-filing-aep-10-q",
    "name": "American Electric Power (AEP): 10-Q",
    "category": "company-filing",
    "url": "/stocks/AEP",
    "metrics": [{"label": "State", "value": None, "unit": "text"}],
    "ticker": "AEP",
    "statesNamed": ["TX"],
}

LOCAL_ROW = {
    "rank": 2,
    "rowId": "local-example",
    "name": "Example County, TX: pause",
    "category": "local",
    "metrics": [{"label": "Ends", "value": "June 30, 2027", "unit": "text"}],
    "endsDate": "2027-06-30",
}

HEATMAP_ROW = {
    "rank": 1,
    "rowId": "NVDA",
    "name": "NVIDIA Corp",
    "category": "Information Technology",
    "url": "/stocks/NVDA",
    "metrics": [],
    "ticker": "NVDA",
    "marketCap": 4400000000000,
    "changePercent": 1.25,
}


class TestTrackerListingFilters:
    def test_filters_parse_to_typed_entries(self):
        resp = TrackerListResponse.from_dict(LISTING)
        dcm = resp.trackers[1]
        assert isinstance(dcm, TrackerListing)
        assert [f.key for f in dcm.filters] == ["category", "state"]
        assert all(isinstance(f, TrackerFilter) for f in dcm.filters)
        assert dcm.filters[0].values == ["federal", "state", "local", "governor", "company-filing"]
        assert "TX" in dcm.filters[1].values

    def test_filters_absent_is_none(self):
        resp = TrackerListResponse.from_dict(LISTING)
        assert resp.trackers[0].filters is None
        # Existing fields are untouched.
        assert resp.trackers[0].canonicalUrl == "/api/v1/trackers/institution-aum"
        assert resp.trackers[0].refreshIntervalSeconds == 86400

    @patch.object(SentiSenseClient, "_get")
    def test_list_trackers_returns_filters(self, mock_get):
        mock_get.return_value = _mock_response(json_data=LISTING)
        resp = SentiSenseClient("k").list_trackers()
        mock_get.assert_called_once_with("/api/v1/trackers")
        assert resp.trackers[1].filters[1].key == "state"


class TestTrackerTableRowNamedCells:
    def test_filing_row_keeps_ticker_url_and_states_named(self):
        row = TrackerTableRow.from_dict(FILING_ROW)
        assert row.ticker == "AEP"
        assert row.url == "/stocks/AEP"
        assert row.statesNamed == ["TX"]
        assert row.endsDate is None

    def test_ends_date_is_kept(self):
        row = TrackerTableRow.from_dict(LOCAL_ROW)
        assert row.endsDate == "2027-06-30"
        assert row.ticker is None
        assert row.url is None
        assert row.statesNamed is None

    def test_untyped_named_cells_survive_in_raw(self):
        row = TrackerTableRow.from_dict(HEATMAP_ROW)
        assert row.ticker == "NVDA"
        assert row.raw["marketCap"] == 4400000000000
        assert row.get("changePercent") == 1.25
        assert row["marketCap"] == 4400000000000
        assert "marketCap" in row
        assert row.get("notAField", "x") == "x"
        assert "notAField" not in row

    def test_typed_fields_win_over_raw_for_item_access(self):
        row = TrackerTableRow.from_dict(FILING_ROW)
        assert row["ticker"] == "AEP"
        assert row["metrics"][0].label == "State"

    def test_missing_item_still_raises_attribute_error(self):
        row = TrackerTableRow.from_dict(LOCAL_ROW)
        with pytest.raises(AttributeError):
            row["notAField"]

    def test_raw_is_hidden_from_repr_and_equality(self):
        a = TrackerTableRow.from_dict(HEATMAP_ROW)
        b = TrackerTableRow.from_dict({**HEATMAP_ROW, "changePercent": -3.0})
        assert a == b
        assert "raw=" not in repr(a)

    def test_snapshot_rows_carry_the_new_fields(self):
        snap = TrackerSnapshot.from_dict(
            {"trackerId": "data-center-moratoriums", "viewType": "table", "rows": [FILING_ROW, LOCAL_ROW]}
        )
        assert [r.ticker for r in snap.rows] == ["AEP", None]
        assert [r.endsDate for r in snap.rows] == [None, "2027-06-30"]


class TestTrackerFilterParam:
    def test_dict_serializes_in_order(self):
        assert _tracker_filter_param({"state": "TX", "category": "local"}) == "state:TX,category:local"

    def test_string_passes_through(self):
        assert _tracker_filter_param("state:TX") == "state:TX"

    def test_other_types_are_rejected(self):
        with pytest.raises(TypeError):
            _tracker_filter_param(["state", "TX"])  # type: ignore[arg-type]

    @patch.object(SentiSenseClient, "_get")
    def test_get_tracker_sends_filter(self, mock_get):
        mock_get.return_value = _mock_response(
            json_data={"isPreview": False, "previewReason": None, "totalCount": 1,
                       "data": {"trackerId": "data-center-moratoriums", "rows": [FILING_ROW]}}
        )
        snap = SentiSenseClient("k").get_tracker("data-center-moratoriums", filter={"state": "TX"})
        mock_get.assert_called_once_with(
            "/api/v1/trackers/data-center-moratoriums", params={"filter": "state:TX"}
        )
        assert snap.total_count == 1
        assert snap.data.rows[0].ticker == "AEP"

    @patch.object(SentiSenseClient, "_get")
    def test_get_tracker_combines_filter_with_other_params(self, mock_get):
        mock_get.return_value = _mock_response(json_data={"isPreview": False, "data": {}})
        SentiSenseClient("k").get_tracker("data-center-moratoriums", filter="state:TX,category:local", scope="x")
        mock_get.assert_called_once_with(
            "/api/v1/trackers/data-center-moratoriums",
            params={"scope": "x", "filter": "state:TX,category:local"},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_existing_calls_are_unchanged(self, mock_get):
        mock_get.return_value = _mock_response(json_data={"isPreview": False, "data": {}})
        client = SentiSenseClient("k")
        client.get_tracker("market-heatmap", scope="nasdaq100")
        mock_get.assert_called_with("/api/v1/trackers/market-heatmap", params={"scope": "nasdaq100"})
        client.get_tracker("institution-aum")
        mock_get.assert_called_with("/api/v1/trackers/institution-aum", params={})


class TestInvalidFilterError:
    def test_invalid_filter_is_an_api_error_with_its_code(self):
        resp = _mock_response(
            status_code=400,
            json_data={"error": "invalid_filter", "message": "Unknown value 'ZZ' for filter 'state'."},
            reason="Bad Request",
        )
        with pytest.raises(APIError) as exc:
            _raise_for_status(resp)
        assert exc.value.status_code == 400
        assert exc.value.code == "invalid_filter"
        assert "ZZ" in exc.value.message

    def test_invalid_scope_is_surfaced_the_same_way(self):
        resp = _mock_response(
            status_code=400,
            json_data={"error": "invalid_scope", "message": "Unknown scope 'zz'."},
            reason="Bad Request",
        )
        with pytest.raises(APIError) as exc:
            _raise_for_status(resp)
        assert exc.value.code == "invalid_scope"
