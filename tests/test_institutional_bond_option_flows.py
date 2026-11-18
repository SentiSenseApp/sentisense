"""Unit tests for ``get_institutional_bond_flows`` and ``get_institutional_option_flows``.

Both take a required quarter date and return the standard preview envelope: a PRO key
gets every row, a free key the top 3 with ``is_preview`` set and ``total_count`` naming
the full list. Contracts gated here:

* ``bondTickers`` is one comma-joined string on the wire, and stays a string.
* The option flows are 13F positions, a different thing from the options analytics
  methods, and the names and text keep the two apart.
"""

import dataclasses
import inspect
import json
import typing
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from sentisense import (
    InstitutionalBondFlow,
    InstitutionalOptionFlow,
    PreviewResult,
    SentiSenseClient,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Bodies built to the captured response shapes with synthetic tickers and values:
# {"pro": ..., "free": ...}.
BONDS = json.loads((FIXTURES / "institutional_bonds.json").read_text())
OPTIONS = json.loads((FIXTURES / "institutional_options.json").read_text())

CASES = [
    ("get_institutional_bond_flows", "/api/v1/institutional/bonds", BONDS, InstitutionalBondFlow),
    ("get_institutional_option_flows", "/api/v1/institutional/options", OPTIONS, InstitutionalOptionFlow),
]
IDS = ["bonds", "options"]


@pytest.fixture
def client():
    return SentiSenseClient("test-api-key")


def _mock_response(json_data):
    resp = MagicMock()
    resp.status_code = 200
    resp.ok = True
    resp.json.return_value = json_data
    return resp


@pytest.mark.parametrize("method, path, bodies, row_cls", CASES, ids=IDS)
class TestBothMethods:
    def test_path_and_report_date_param(self, method, path, bodies, row_cls, client):
        with patch.object(SentiSenseClient, "_get") as mock_get:
            mock_get.return_value = _mock_response(bodies["pro"])
            getattr(client, method)("2025-12-31")
        mock_get.assert_called_once_with(path, params={"reportDate": "2025-12-31"})

    def test_full_url_through_the_session(self, method, path, bodies, row_cls, client):
        with patch.object(client.session, "get", return_value=_mock_response(bodies["pro"])) as get:
            getattr(client, method)(report_date="2026-06-30")
        assert get.call_args[0][0] == "https://app.sentisense.ai" + path
        assert get.call_args[1]["params"] == {"reportDate": "2026-06-30"}

    def test_report_date_is_required(self, method, path, bodies, row_cls, client):
        param = inspect.signature(getattr(SentiSenseClient, method)).parameters["report_date"]
        assert param.default is inspect.Parameter.empty
        with pytest.raises(TypeError):
            getattr(client, method)()

    def test_pro_body(self, method, path, bodies, row_cls, client):
        with patch.object(SentiSenseClient, "_get", return_value=_mock_response(bodies["pro"])):
            result = getattr(client, method)("2025-12-31")

        assert isinstance(result, PreviewResult)
        assert result.is_preview is False
        assert result.preview_reason is None
        assert result.total_count is None
        assert result.upgrade is None
        assert len(result) == len(bodies["pro"]["data"])
        assert all(isinstance(row, row_cls) for row in result)

    def test_free_preview_of_three(self, method, path, bodies, row_cls, client):
        with patch.object(SentiSenseClient, "_get", return_value=_mock_response(bodies["free"])):
            result = getattr(client, method)("2025-12-31")

        assert result.is_preview is True
        assert result.preview_reason == "PRO_REQUIRED"
        assert len(result.data) == 3
        assert result.total_count == len(bodies["pro"]["data"])
        assert result.total_count > len(result.data)
        assert result.upgrade["plan"] == "PRO"
        assert all(isinstance(row, row_cls) for row in result.data)
        # The preview is the head of the full list, in the same order.
        assert [dataclasses.asdict(r) for r in result] == bodies["pro"]["data"][:3]

    def test_every_wire_key_is_declared(self, method, path, bodies, row_cls, client):
        with patch.object(SentiSenseClient, "_get", return_value=_mock_response(bodies["pro"])):
            rows = list(getattr(client, method)("2025-12-31"))
        declared = {f.name for f in dataclasses.fields(row_cls)}
        for raw, row in zip(bodies["pro"]["data"], rows):
            assert set(raw) == declared
            assert dict(row.extra_fields) == {}

    def test_empty_quarter(self, method, path, bodies, row_cls, client):
        empty = {"isPreview": False, "previewReason": None, "data": []}
        with patch.object(SentiSenseClient, "_get", return_value=_mock_response(empty)):
            result = getattr(client, method)("2013-03-31")
        assert result.data == []
        assert len(result) == 0 and not result

    def test_undeclared_keys_are_kept(self, method, path, bodies, row_cls, client):
        body = json.loads(json.dumps(bodies["free"]))
        body["data"][0]["zzNew"] = 7
        with patch.object(SentiSenseClient, "_get", return_value=_mock_response(body)):
            result = getattr(client, method)("2025-12-31")
        assert result.data[0].get("zzNew") == 7
        assert result.data[0].zzNew == 7

    def test_no_row_field_is_named_data(self, method, path, bodies, row_cls, client):
        assert "data" not in {f.name for f in dataclasses.fields(row_cls)}


class TestBondTickers:
    def test_is_one_comma_joined_string(self, client):
        with patch.object(SentiSenseClient, "_get", return_value=_mock_response(BONDS["pro"])):
            first = client.get_institutional_bond_flows("2025-12-31")[0]
        assert isinstance(first.bondTickers, str)
        assert first.bondTickers == "EXMA 0 03/15/30, EXMA 0.5 06/15/31"
        assert [t.strip() for t in first.bondTickers.split(",")] == [
            "EXMA 0 03/15/30", "EXMA 0.5 06/15/31",
        ]

    def test_is_typed_as_a_string(self):
        assert typing.get_type_hints(InstitutionalBondFlow)["bondTickers"] == Optional[str]

    def test_null_company_name_reads_none(self):
        row = next(r for r in BONDS["pro"]["data"] if r["companyName"] is None)
        assert InstitutionalBondFlow.from_dict(row).companyName is None


class TestOptionFlowsAreNotTheOptionsAnalytics:
    def test_docstring_points_at_the_analytics_methods(self):
        doc = SentiSenseClient.get_institutional_option_flows.__doc__ or ""
        assert "13F" in doc
        assert "get_options_overview" in doc and "get_stock_options_summary" in doc

    def test_names_stay_outside_the_options_family(self):
        assert not InstitutionalOptionFlow.__name__.startswith("Options")
        assert not SentiSenseClient.get_institutional_option_flows.__name__.startswith("get_options")

    def test_rows_carry_call_and_put_sides(self, client):
        with patch.object(SentiSenseClient, "_get", return_value=_mock_response(OPTIONS["pro"])):
            first = client.get_institutional_option_flows("2025-12-31")[0]
        assert (first.ticker, first.callValue, first.putValue) == ("EXMA", 2000000000, 1500000000)
        assert (first.callPositions, first.putPositions, first.hedgeFundCount) == (150, 100, 40)
        assert (first.callNetChange, first.putNetChange) == (10000000, 8000000)
