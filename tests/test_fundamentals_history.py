"""get_fundamentals_history: the request it sends and the provenance it passes through.

The fixture keeps the live response's keys with synthetic values: one period served
from an SEC-backed record with SEC-sourced lines, one served from that record with
every line from the data provider, and one with no provenance keys at all, which is
what most periods look like.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sentisense import (
    FundamentalsHistory,
    FundamentalsLineSource,
    FundamentalsStatement,
    SentiSenseClient,
)

FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures" / "fundamentals_history.json").read_text()
)
PROVENANCE = ("source", "sourceRef", "secFiled", "lineSources")


def _call(payload, *args, **kwargs):
    client = SentiSenseClient("test-api-key")
    response = MagicMock(status_code=200, ok=True)
    response.json.return_value = payload
    with patch.object(client, "_get", return_value=response) as get:
        result = client.get_fundamentals_history(*args, **kwargs)
    return result, get


class TestRequest:
    def test_defaults_send_only_the_ticker(self):
        _, get = _call(FIXTURES["history"], "EXMP")
        get.assert_called_once_with(
            "/api/v1/stocks/fundamentals/history", params={"ticker": "EXMP"}
        )

    def test_timeframe_and_limit_are_forwarded(self):
        _, get = _call(FIXTURES["history"], "EXMP", timeframe="annual", limit=5)
        get.assert_called_once_with(
            "/api/v1/stocks/fundamentals/history",
            params={"ticker": "EXMP", "timeframe": "annual", "limit": 5},
        )


class TestResponse:
    def test_returns_the_envelope_as_received(self):
        result, _ = _call(FIXTURES["history"], "EXMP")
        assert result == FIXTURES["history"]
        assert result["count"] == len(result["periods"]) == 3

    def test_sec_backed_period_names_its_filing_and_lines(self):
        result, _ = _call(FIXTURES["history"], "EXMP")
        period = result["periods"][0]
        assert period["source"] == "SEC"
        assert period["sourceRef"] == "0000000001-26-000002"
        assert period["secFiled"] == "2026-11-04"
        line = period["lineSources"]["revenue"]
        assert line == {"source": "SEC", "accession": "0000000001-26-000002", "filed": "2026-11-04"}

    def test_provider_period_has_source_but_no_line_list(self):
        result, _ = _call(FIXTURES["history"], "EXMP")
        period = result["periods"][1]
        assert period["source"] == "PROVIDER"
        for key in ("sourceRef", "secFiled", "lineSources"):
            assert key not in period

    def test_provenance_is_absent_not_null_on_other_periods(self):
        result, _ = _call(FIXTURES["history"], "EXMP")
        period = result["periods"][2]
        for key in PROVENANCE:
            assert key not in period
            assert period.get(key) is None

    def test_a_ticker_without_statements_is_an_empty_answer(self):
        result, _ = _call(FIXTURES["empty"], "EXMPF")
        assert result["count"] == 0
        assert result["periods"] == []
        assert result["reason"]


class TestAnnotations:
    def test_the_period_annotation_covers_every_key_the_api_sends(self):
        declared = set(FundamentalsStatement.__annotations__)
        for period in FIXTURES["history"]["periods"]:
            assert not set(period) - declared, sorted(set(period) - declared)

    @pytest.mark.parametrize(
        "annotation", [FundamentalsHistory, FundamentalsStatement, FundamentalsLineSource]
    )
    def test_annotations_require_no_key(self, annotation):
        assert annotation.__total__ is False
        assert annotation() == {}

    def test_line_source_annotation_names_the_wire_keys(self):
        assert set(FundamentalsLineSource.__annotations__) == {"source", "accession", "filed"}
        assert set(FundamentalsHistory.__annotations__) == {
            "ticker", "timeframe", "count", "dataSource", "reason", "periods"
        }
        assert set(PROVENANCE) <= set(FundamentalsStatement.__annotations__)
