"""Unit tests for ``get_sentiment_breadth`` and ``get_sentiment_sectors``.

Both return a bare object, not a preview envelope: every tier receives the same body.
Contracts gated here:

* ``latest`` on breadth is the newest entry of ``series``, parsed into the same row
  type in both places.
* Fields the server cannot fill are omitted from the JSON and read as ``None``, never
  as zero (a dispersion of ``0`` would claim the market agrees with itself).
* Before the first pipeline run of a snapshot the body is empty, and the models read
  that as ``latest is None`` and empty lists rather than raising.
"""

import dataclasses
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sentisense import (
    PreviewResult,
    SentimentBreadth,
    SentimentBreadthBucket,
    SentimentSector,
    SentimentSectors,
    SentimentStockRef,
    SentiSenseClient,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# The live response shapes, key for key, with synthetic values: breadth with six series
# days, sectors with six sectors and made-up member tickers.
BREADTH = json.loads((FIXTURES / "sentiment_breadth.json").read_text())
SECTORS = json.loads((FIXTURES / "sentiment_sectors.json").read_text())


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


class TestBreadthRequest:
    @patch.object(SentiSenseClient, "_get")
    def test_path_and_no_params(self, mock_get, client):
        mock_get.return_value = _mock_response(BREADTH)
        client.get_sentiment_breadth()
        mock_get.assert_called_once_with("/api/v1/sentiment/breadth")

    def test_full_url_through_the_session(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(BREADTH)) as get:
            client.get_sentiment_breadth()
        assert get.call_args[0][0] == "https://app.sentisense.ai/api/v1/sentiment/breadth"


class TestBreadthParsing:
    @patch.object(SentiSenseClient, "_get")
    def test_returns_the_bare_typed_object(self, mock_get, client):
        mock_get.return_value = _mock_response(BREADTH)
        breadth = client.get_sentiment_breadth()

        assert isinstance(breadth, SentimentBreadth)
        assert not isinstance(breadth, PreviewResult)
        assert breadth.schemaVersion == "1.0"
        assert breadth.generatedAt == 1768086000  # epoch seconds
        assert breadth.asOf == "2026-01-10"
        assert breadth.minMentions == 5
        assert isinstance(breadth.latest, SentimentBreadthBucket)
        assert len(breadth.series) == 6
        assert all(isinstance(b, SentimentBreadthBucket) for b in breadth.series)

    @patch.object(SentiSenseClient, "_get")
    def test_latest_is_the_newest_entry_of_series(self, mock_get, client):
        mock_get.return_value = _mock_response(BREADTH)
        breadth = client.get_sentiment_breadth()

        dates = [b.date for b in breadth.series]
        assert dates == sorted(dates), "series runs oldest to newest"
        assert breadth.latest == breadth.series[-1]
        assert type(breadth.latest) is type(breadth.series[-1])

    @patch.object(SentiSenseClient, "_get")
    def test_bucket_values_and_units(self, mock_get, client):
        mock_get.return_value = _mock_response(BREADTH)
        latest = client.get_sentiment_breadth().latest

        assert (latest.coveredStocks, latest.bullish, latest.neutral, latest.bearish) == (400, 240, 80, 80)
        assert latest.bullish + latest.neutral + latest.bearish == latest.coveredStocks
        assert latest.bullishPct == 60.0  # percent, not a fraction
        assert latest.bullishPct + latest.neutralPct + latest.bearishPct == pytest.approx(100, abs=0.05)
        assert latest.netBreadth == pytest.approx(latest.bullishPct - latest.bearishPct, abs=0.01)
        assert latest.bullishMentionPct == 60.0
        assert latest.sentimentDispersion == 0.4

    @patch.object(SentiSenseClient, "_get")
    def test_every_wire_key_is_declared(self, mock_get, client):
        mock_get.return_value = _mock_response(BREADTH)
        breadth = client.get_sentiment_breadth()

        assert set(BREADTH) <= _declared(SentimentBreadth)
        assert set(BREADTH["latest"]) <= _declared(SentimentBreadthBucket)
        assert dict(breadth.extra_fields) == {}
        assert dict(breadth.latest.extra_fields) == {}

    def test_omitted_dispersion_reads_none(self):
        bucket = dict(BREADTH["latest"])
        del bucket["sentimentDispersion"]
        assert SentimentBreadthBucket.from_dict(bucket).sentimentDispersion is None
        assert SentimentBreadthBucket.from_dict(
            dict(bucket, sentimentDispersion=None)
        ).sentimentDispersion is None

    @pytest.mark.parametrize(
        "body",
        [{}, {"schemaVersion": "1.0", "series": []}, {"latest": None, "series": None}],
        ids=["empty", "no-latest", "nulls"],
    )
    def test_empty_snapshot(self, body):
        breadth = SentimentBreadth.from_dict(body)
        assert breadth.latest is None
        assert breadth.series == []
        assert breadth.generatedAt is None

    def test_undeclared_keys_are_kept(self):
        body = json.loads(json.dumps(BREADTH))
        body["zzNew"] = 1
        body["latest"]["zzNew"] = 2
        body["series"][0]["zzNew"] = 3
        breadth = SentimentBreadth.from_dict(body)
        assert breadth.get("zzNew") == 1
        assert breadth.latest["zzNew"] == 2
        assert breadth.series[0].zzNew == 3


class TestSectorsRequest:
    @patch.object(SentiSenseClient, "_get")
    def test_path_and_no_params(self, mock_get, client):
        mock_get.return_value = _mock_response(SECTORS)
        client.get_sentiment_sectors()
        mock_get.assert_called_once_with("/api/v1/sentiment/sectors")


class TestSectorsParsing:
    @patch.object(SentiSenseClient, "_get")
    def test_returns_the_bare_typed_object(self, mock_get, client):
        mock_get.return_value = _mock_response(SECTORS)
        snap = client.get_sentiment_sectors()

        assert isinstance(snap, SentimentSectors)
        assert not isinstance(snap, PreviewResult)
        assert snap.generatedAt == 1768086000
        assert snap.asOf == "2026-01-10"
        assert snap.marketConsensusRatio == 0.2
        assert snap.narrative == "Synthetic example narrative: one sector leads and one lags."
        assert len(snap.sectors) == 6
        assert all(isinstance(s, SentimentSector) for s in snap.sectors)

    @patch.object(SentiSenseClient, "_get")
    def test_sector_row_and_stock_refs(self, mock_get, client):
        mock_get.return_value = _mock_response(SECTORS)
        energy = client.get_sentiment_sectors().sectors[0]

        assert energy.sector == "Energy"
        assert (energy.label, energy.scoreLabel, energy.consensusLabel) == (
            "Bullish", "Slightly Bullish", "Hotter than market",
        )
        assert energy.consensusVsMarket == pytest.approx(
            energy.consensusRatio - 0.2, abs=0.0001
        )
        assert isinstance(energy.topStock, SentimentStockRef)
        assert (energy.topStock.ticker, energy.topStock.value) == ("EXMA", 0.9)
        assert (energy.bottomStock.ticker, energy.bottomStock.value) == ("EXMB", -0.5)
        assert (energy.bullMentions, energy.bearMentions) == (700, 300)
        assert (energy.stockCount, energy.totalMentions) == (100, 5000)

    @patch.object(SentiSenseClient, "_get")
    def test_every_wire_key_is_declared(self, mock_get, client):
        mock_get.return_value = _mock_response(SECTORS)
        snap = client.get_sentiment_sectors()

        assert set(SECTORS) <= _declared(SentimentSectors)
        for raw, row in zip(SECTORS["sectors"], snap.sectors):
            assert set(raw) <= _declared(SentimentSector)
            assert dict(row.extra_fields) == {}
            assert set(raw["topStock"]) <= _declared(SentimentStockRef)

    def test_omitted_fields_read_none(self):
        row = SentimentSector.from_dict({"sector": "Utilities"})
        assert row.topStock is None and row.bottomStock is None
        assert row.meanScore is None and row.consensusVsMarket is None

    @pytest.mark.parametrize("body", [{}, {"sectors": []}, {"sectors": None}],
                             ids=["empty", "no-sectors", "null"])
    def test_empty_snapshot(self, body):
        assert SentimentSectors.from_dict(body).sectors == []

    def test_undeclared_keys_are_kept(self):
        body = json.loads(json.dumps(SECTORS))
        body["zzNew"] = 1
        body["sectors"][0]["zzNew"] = 2
        body["sectors"][0]["topStock"]["zzNew"] = 3
        snap = SentimentSectors.from_dict(body)
        assert snap["zzNew"] == 1
        assert snap.sectors[0].get("zzNew") == 2
        assert snap.sectors[0].topStock.zzNew == 3
