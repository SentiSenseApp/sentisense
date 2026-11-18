"""Unit tests for ``get_metrics_slices``.

Contracts gated here:

* Slices is a bare array, and a metric with no slices answers ``[]``.
* Each path argument is sent as exactly one path segment. A reserved character in
  either argument (``?``, ``#``, ``/``, a space) is percent-encoded, so it can never
  move the request to another route or drop the rest of the path.
* An argument that cannot be held in one segment (empty, whitespace only, ``.`` or
  ``..``) raises ``ValueError`` before any request is sent.
* The entity id the server strips is never declared.
"""

import dataclasses
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import urlsplit

import pytest
import requests

from sentisense import MetricSlice, PreviewResult, SentiSenseClient

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# A body built to the captured response shape, with synthetic values.
SLICES = json.loads((FIXTURES / "metric_slices.json").read_text())


@pytest.fixture
def client():
    return SentiSenseClient("test-api-key")


def _mock_response(json_data):
    resp = MagicMock()
    resp.status_code = 200
    resp.ok = True
    resp.json.return_value = json_data
    return resp


def _declared(cls):
    return {f.name for f in dataclasses.fields(cls)}


def _prepared_url(client, symbol, metric_type):
    """The URL requests would put on the wire for this call."""
    with patch.object(client.session, "get", return_value=_mock_response([])) as get:
        client.get_metrics_slices(symbol, metric_type)
    return requests.Request("GET", get.call_args[0][0]).prepare().url


class TestRequest:
    @patch.object(SentiSenseClient, "_get")
    def test_path_and_no_params(self, mock_get, client):
        mock_get.return_value = _mock_response(SLICES)
        client.get_metrics_slices("EXMP", "sentiment")
        mock_get.assert_called_once_with("/api/v2/metrics/entity/EXMP/metric/sentiment/slices")

    @patch.object(SentiSenseClient, "_get")
    def test_entity_slug_goes_in_the_path(self, mock_get, client):
        mock_get.return_value = _mock_response([])
        client.get_metrics_slices(symbol="Example-Entity", metric_type="mentions")
        mock_get.assert_called_once_with("/api/v2/metrics/entity/Example-Entity/metric/mentions/slices")

    @pytest.mark.parametrize(
        "symbol, metric_type",
        [("EXMP", "sentiment"), ("BRK.B", "mentions"), ("Example-Entity", "sentisense_score")],
    )
    def test_safe_arguments_are_sent_unchanged(self, client, symbol, metric_type):
        url = _prepared_url(client, symbol, metric_type)
        assert url == "https://app.sentisense.ai/api/v2/metrics/entity/%s/metric/%s/slices" % (
            symbol, metric_type,
        )

    @pytest.mark.parametrize(
        "symbol, metric_type, symbol_segment, metric_segment",
        [
            ("EXMP", "sentiment?x=y", "EXMP", "sentiment%3Fx%3Dy"),
            ("EXMP#ignored", "sentiment", "EXMP%23ignored", "sentiment"),
            ("EXMP/extra", "sentiment", "EXMP%2Fextra", "sentiment"),
            ("Example Entity", "mentions", "Example%20Entity", "mentions"),
            ("EXMP", "a/b#c?d", "EXMP", "a%2Fb%23c%3Fd"),
        ],
        ids=["question-mark", "hash", "slash", "space", "all-three"],
    )
    def test_reserved_characters_stay_inside_their_segment(
        self, client, symbol, metric_type, symbol_segment, metric_segment
    ):
        url = _prepared_url(client, symbol, metric_type)
        parts = urlsplit(url)
        assert parts.query == "" and parts.fragment == ""
        assert parts.path == "/api/v2/metrics/entity/%s/metric/%s/slices" % (
            symbol_segment, metric_segment,
        )
        assert parts.path.split("/")[1:] == [
            "api", "v2", "metrics", "entity", symbol_segment, "metric", metric_segment, "slices",
        ]


class TestArgumentValidation:
    @pytest.mark.parametrize("bad", ["", "   ", ".", ".."], ids=["empty", "blank", "dot", "dot-dot"])
    @pytest.mark.parametrize("position", ["symbol", "metric_type"])
    def test_rejected_before_any_request(self, client, position, bad):
        args = {"symbol": "EXMP", "metric_type": "sentiment"}
        args[position] = bad
        with patch.object(client.session, "get") as get, patch.object(SentiSenseClient, "_get") as _get:
            with pytest.raises(ValueError) as caught:
                client.get_metrics_slices(**args)
        get.assert_not_called()
        _get.assert_not_called()
        assert str(caught.value) == "%s must not be empty, '.' or '..'; got %r" % (position, bad)

    @pytest.mark.parametrize(
        "symbol, metric_type", [("EXMP", "sentiment"), ("BRK.B", "sentiment"), ("EXMP", "mentions")]
    )
    def test_normal_arguments_pass(self, client, symbol, metric_type):
        url = _prepared_url(client, symbol, metric_type)
        assert urlsplit(url).path == "/api/v2/metrics/entity/%s/metric/%s/slices" % (symbol, metric_type)

    @pytest.mark.parametrize(
        "symbol, metric_type",
        [("BRK.B", "mentions"), ("a..b", "mentions"), ("EXMP", "a..b"), ("...", "mentions")],
        ids=["one-dot", "double-dot-inside", "double-dot-inside-metric", "three-dots"],
    )
    def test_values_containing_dots_stay_in_their_slot(self, client, symbol, metric_type):
        url = _prepared_url(client, symbol, metric_type)
        assert urlsplit(url).path.split("/")[1:] == [
            "api", "v2", "metrics", "entity", symbol, "metric", metric_type, "slices",
        ]


class TestParsing:
    @patch.object(SentiSenseClient, "_get")
    def test_parses_a_bare_array(self, mock_get, client):
        mock_get.return_value = _mock_response(SLICES)
        slices = client.get_metrics_slices("EXMP", "sentiment")

        assert isinstance(slices, list) and not isinstance(slices, PreviewResult)
        assert all(isinstance(s, MetricSlice) for s in slices)
        source = slices[0]
        assert (source.metricType, source.dimension, source.displayName) == ("sentiment", "source", "Source")
        assert "Reddit" in source.values

    @patch.object(SentiSenseClient, "_get")
    def test_no_slices_is_an_empty_list(self, mock_get, client):
        mock_get.return_value = _mock_response([])
        assert client.get_metrics_slices("EXMP", "sentisense_score") == []

    def test_every_wire_key_is_declared(self):
        for raw in SLICES:
            assert set(raw) == _declared(MetricSlice)
            assert dict(MetricSlice.from_dict(raw).extra_fields) == {}

    def test_the_entity_id_is_never_declared(self):
        assert "entityId" not in _declared(MetricSlice)

    def test_null_values_read_as_an_empty_list(self):
        assert MetricSlice.from_dict({"dimension": "source", "values": None}).values == []
        assert MetricSlice.from_dict({}).dimension is None

    def test_undeclared_keys_are_kept(self):
        row = MetricSlice.from_dict(dict(SLICES[0], zzNew=1))
        assert row.get("zzNew") == 1
