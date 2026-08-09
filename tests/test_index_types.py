"""Unit tests for the Indexes resource.

The contract worth gating here is the two-archetype envelope. A basket index
(fed-sentiment, ai-sentiment) fills ``constituents`` / ``basketSize`` /
``coverage`` / ``totalMentions``; a composite index (market-mood) returns
``None`` for all four *by construction*, because it is built from signals rather
than entities. A client that coerces those to ``0`` or ``[]`` loses the
distinction and renders a basket UI for a composite index, so the None-ness is
asserted explicitly rather than assumed.
"""

from unittest.mock import MagicMock, patch

import pytest

from sentisense import SentiSenseClient
from sentisense.types import (
    IndexHistoryResponse,
    IndexListResponse,
    IndexSnapshot,
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


BASKET_SNAPSHOT = {
    "indexId": "fed-sentiment",
    "displayName": "Fed Sentiment",
    "asOf": "2026-06-01",
    "value": 0.12,
    "scale": "SENTIMENT",
    "coverage": 3,
    "basketSize": 3,
    "totalMentions": 480,
    "methodologyNote": "Weekly composite.",
    "constituents": [
        {
            "kbEntityId": "kb/person/1",
            "displayName": "Example",
            "role": "Chair",
            "weight": 3.0,
            "value": 0.15,
            "mentionsCount": 260,
            "staleness": "FRESH",
            "contribution": None,
            "link": None,
        }
    ],
}

COMPOSITE_SNAPSHOT = {
    "indexId": "market-mood",
    "displayName": "Market Mood",
    "asOf": "2026-08-07",
    "value": 66.2,
    "scale": "PERCENT_0_100",
    "coverage": None,
    "basketSize": None,
    "totalMentions": None,
    "methodologyNote": "Five-signal composite.",
    "constituents": None,
}


class TestListIndexes:
    @patch.object(SentiSenseClient, "_get")
    def test_calls_discovery_path(self, mock_get, client):
        mock_get.return_value = _mock_response({"indexes": []})
        result = client.list_indexes()
        mock_get.assert_called_once_with("/api/v1/indexes")
        assert isinstance(result, IndexListResponse)
        assert result.indexes == []

    @patch.object(SentiSenseClient, "_get")
    def test_parses_listings(self, mock_get, client):
        mock_get.return_value = _mock_response(
            {
                "indexes": [
                    {
                        "indexId": "fed-sentiment",
                        "displayName": "Fed Sentiment",
                        "description": "Weekly composite.",
                        "scale": "SENTIMENT",
                        "accessTier": "free",
                        "canonicalUrl": "/api/v1/indexes/fed-sentiment",
                    },
                    {
                        "indexId": "market-mood",
                        "displayName": "Market Mood",
                        "description": "0-100 composite.",
                        "scale": "PERCENT_0_100",
                        "accessTier": "free",
                        "canonicalUrl": "/api/v2/market-mood",
                    },
                ]
            }
        )
        result = client.list_indexes()
        assert [i.indexId for i in result.indexes] == ["fed-sentiment", "market-mood"]
        assert result.indexes[0].accessTier == "free"
        # Market Mood's canonicalUrl deliberately points at its richer view rather
        # than the detail route. A client must not rewrite it.
        assert result.indexes[1].canonicalUrl == "/api/v2/market-mood"

    @patch.object(SentiSenseClient, "_get")
    def test_tolerates_missing_indexes_key(self, mock_get, client):
        mock_get.return_value = _mock_response({})
        assert client.list_indexes().indexes == []


class TestGetIndex:
    @patch.object(SentiSenseClient, "_get")
    def test_includes_index_id_in_path(self, mock_get, client):
        mock_get.return_value = _mock_response(BASKET_SNAPSHOT)
        client.get_index("fed-sentiment")
        mock_get.assert_called_once_with("/api/v1/indexes/fed-sentiment")

    @patch.object(SentiSenseClient, "_get")
    def test_basket_index_keeps_its_breakdown(self, mock_get, client):
        mock_get.return_value = _mock_response(BASKET_SNAPSHOT)
        snap = client.get_index("fed-sentiment")
        assert isinstance(snap, IndexSnapshot)
        assert snap.coverage == 3
        assert snap.basketSize == 3
        assert snap.totalMentions == 480
        assert len(snap.constituents) == 1
        assert snap.constituents[0].staleness == "FRESH"
        assert snap.constituents[0].weight == 3.0
        # Reserved by the API and not populated today; must tolerate None.
        assert snap.constituents[0].contribution is None

    @patch.object(SentiSenseClient, "_get")
    def test_composite_index_nulls_survive(self, mock_get, client):
        mock_get.return_value = _mock_response(COMPOSITE_SNAPSHOT)
        snap = client.get_index("market-mood")
        assert snap.value == 66.2
        assert snap.coverage is None
        assert snap.basketSize is None
        assert snap.totalMentions is None
        assert snap.constituents is None
        assert snap.methodologyNote

    @patch.object(SentiSenseClient, "_get")
    def test_empty_basket_is_not_a_composite(self, mock_get, client):
        """``[]`` and ``None`` mean different things and must not be collapsed.

        An empty list is a basket index with nothing contributing today; ``None``
        is an index that has no constituents at all. Collapsing them would make a
        data outage look like an archetype.
        """
        mock_get.return_value = _mock_response({**BASKET_SNAPSHOT, "constituents": []})
        snap = client.get_index("fed-sentiment")
        assert snap.constituents == []
        assert snap.constituents is not None


class TestGetIndexHistory:
    @patch.object(SentiSenseClient, "_get")
    def test_defaults_to_180_days(self, mock_get, client):
        mock_get.return_value = _mock_response({"indexId": "fed-sentiment", "history": []})
        client.get_index_history("fed-sentiment")
        mock_get.assert_called_once_with(
            "/api/v1/indexes/fed-sentiment/history", params={"days": 180}
        )

    @patch.object(SentiSenseClient, "_get")
    def test_passes_days_through(self, mock_get, client):
        mock_get.return_value = _mock_response({"indexId": "fed-sentiment", "history": []})
        client.get_index_history("fed-sentiment", days=30)
        mock_get.assert_called_once_with(
            "/api/v1/indexes/fed-sentiment/history", params={"days": 30}
        )

    @patch.object(SentiSenseClient, "_get")
    def test_parses_points_in_order(self, mock_get, client):
        mock_get.return_value = _mock_response(
            {
                "indexId": "fed-sentiment",
                "displayName": "Fed Sentiment",
                "scale": "SENTIMENT",
                "days": 180,
                "history": [
                    {"date": "2026-05-18", "value": 0.08},
                    {"date": "2026-05-25", "value": 0.12},
                ],
            }
        )
        result = client.get_index_history("fed-sentiment")
        assert isinstance(result, IndexHistoryResponse)
        assert [p.date for p in result.history] == ["2026-05-18", "2026-05-25"]
        assert result.history[1].value == 0.12
        assert result.days == 180

    @patch.object(SentiSenseClient, "_get")
    def test_tolerates_gaps_and_null_values(self, mock_get, client):
        """Withheld buckets mean the series can be sparse; a null point is valid."""
        mock_get.return_value = _mock_response(
            {"indexId": "ai-sentiment", "history": [{"date": "2026-05-18", "value": None}]}
        )
        result = client.get_index_history("ai-sentiment")
        assert result.history[0].value is None
