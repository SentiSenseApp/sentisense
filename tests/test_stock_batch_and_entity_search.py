"""Unit tests for entity search, the batch stock lookups, popular stocks and the metric breakdown.

The batch lookups answer with a dict keyed by ticker and simply leave out a ticker they
have nothing for, so a caller indexing the result by every ticker it sent gets a
``KeyError``. Those absences, and the empty search result, are pinned here alongside the
request each method sends. Every test mocks the HTTP layer; none touches the network.
"""

import inspect
from unittest.mock import MagicMock, patch

import pytest

from sentisense import APIError, EntitySearchResult, SentiSenseClient, StockImage
from sentisense.types import StockDetail


@pytest.fixture
def client():
    return SentiSenseClient("test-api-key")


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.reason = "OK" if resp.ok else "Bad Request"
    resp.json.return_value = json_data
    return resp


ICON = "https://app.sentisense.ai/api/v1/stocks/proxy-image?ticker=EXMP&id=icon"
LOGO = "https://app.sentisense.ai/api/v1/stocks/proxy-image?ticker=EXMP&id=logo"
FUND_ICON = "https://app.sentisense.ai/api/v1/stocks/proxy-image?ticker=EXMF&id=icon"


class TestSearchEntities:
    @patch.object(SentiSenseClient, "_get")
    def test_sends_only_the_query_by_default(self, mock_get, client):
        mock_get.return_value = _mock_response([])
        client.search_entities("pelosi")
        mock_get.assert_called_once_with("/api/v1/kb/entities/search", params={"q": "pelosi"})

    @patch.object(SentiSenseClient, "_get")
    def test_passes_type_and_limit(self, mock_get, client):
        mock_get.return_value = _mock_response([])
        client.search_entities("pelosi", type="person", limit=3)
        mock_get.assert_called_once_with(
            "/api/v1/kb/entities/search",
            params={"q": "pelosi", "type": "person", "limit": 3},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_parses_each_kind_of_match(self, mock_get, client):
        mock_get.return_value = _mock_response(
            [
                {"name": "Example Person", "urlSlug": "Example-Person", "type": "person",
                 "ticker": None},
                {"name": "Example Corp", "urlSlug": "Example-Corp", "type": "company",
                 "ticker": "EXMP", "listingCoverage": "public_tracked"},
                {"name": "Overseas Example Co", "urlSlug": "Overseas-Example-Co",
                 "type": "company", "ticker": None, "listingCoverage": "public_untracked",
                 "listing": "KRX: 000000"},
            ]
        )

        person, tracked, untracked = client.search_entities("example")

        assert all(isinstance(hit, EntitySearchResult) for hit in (person, tracked, untracked))
        assert (person.name, person.urlSlug, person.type) == (
            "Example Person", "Example-Person", "person")
        assert person.ticker is None and person.listingCoverage is None
        assert tracked.ticker == "EXMP" and tracked.listingCoverage == "public_tracked"
        assert tracked.listing is None
        assert untracked.ticker is None
        assert untracked.listingCoverage == "public_untracked"
        assert untracked.listing == "KRX: 000000"
        assert dict(untracked.extra_fields) == {}

    @patch.object(SentiSenseClient, "_get")
    def test_no_match_is_an_empty_list(self, mock_get, client):
        mock_get.return_value = _mock_response([])
        assert client.search_entities("qqzzxx") == []

    def test_a_short_query_raises_api_error_with_the_code(self, client):
        response = _mock_response(
            {"error": "invalid_parameter",
             "message": "Query parameter 'q' must be at least 2 characters."},
            status_code=400,
        )
        with patch.object(client.session, "get", return_value=response):
            with pytest.raises(APIError) as caught:
                client.search_entities("a")
        assert caught.value.status_code == 400
        assert caught.value.code == "invalid_parameter"


class TestGetStockImages:
    @patch.object(SentiSenseClient, "_get")
    def test_joins_tickers_and_omits_forced_by_default(self, mock_get, client):
        mock_get.return_value = _mock_response({})
        client.get_stock_images(["EXMP", "EXMF", "EXMQ"])
        mock_get.assert_called_once_with(
            "/api/v1/stocks/images", params={"tickers": "EXMP,EXMF,EXMQ"}
        )

    @patch.object(SentiSenseClient, "_get")
    def test_passes_forced(self, mock_get, client):
        mock_get.return_value = _mock_response({})
        client.get_stock_images(["EXMP"], forced=True)
        mock_get.assert_called_once_with(
            "/api/v1/stocks/images", params={"tickers": "EXMP", "forced": True}
        )

    @patch.object(SentiSenseClient, "_get")
    def test_returns_typed_images_keyed_by_ticker(self, mock_get, client):
        mock_get.return_value = _mock_response(
            {"EXMP": {"iconUrl": ICON, "logoUrl": LOGO}, "EXMF": {"iconUrl": FUND_ICON}}
        )

        images = client.get_stock_images(["EXMP", "EXMF"])

        assert set(images) == {"EXMP", "EXMF"}
        assert isinstance(images["EXMP"], StockImage)
        assert images["EXMP"].iconUrl == ICON and images["EXMP"].logoUrl == LOGO
        # A fund carries only its fund-family icon.
        assert images["EXMF"].iconUrl == FUND_ICON and images["EXMF"].logoUrl is None

    @patch.object(SentiSenseClient, "_get")
    def test_a_ticker_without_an_image_is_absent(self, mock_get, client):
        mock_get.return_value = _mock_response({"EXMP": {"iconUrl": ICON, "logoUrl": LOGO}})

        images = client.get_stock_images(["EXMP", "QQZZX"])

        assert "QQZZX" not in images
        assert images.get("QQZZX") is None

    @patch.object(SentiSenseClient, "_get")
    def test_an_empty_response_is_an_empty_dict(self, mock_get, client):
        mock_get.return_value = _mock_response({})
        assert client.get_stock_images(["QQZZX"]) == {}


class TestGetStockDescriptions:
    @patch.object(SentiSenseClient, "_get")
    def test_joins_tickers_and_sends_forced_only_when_true(self, mock_get, client):
        mock_get.return_value = _mock_response({})
        client.get_stock_descriptions(["EXMP", "EXMQ"])
        client.get_stock_descriptions(["EXMP"], forced=False)
        client.get_stock_descriptions(["EXMP"], forced=True)
        assert mock_get.call_args_list[0].args == ("/api/v1/stocks/descriptions",)
        assert mock_get.call_args_list[0].kwargs == {"params": {"tickers": "EXMP,EXMQ"}}
        assert mock_get.call_args_list[1].kwargs == {"params": {"tickers": "EXMP"}}
        assert mock_get.call_args_list[2].kwargs == {
            "params": {"tickers": "EXMP", "forced": True}
        }

    @patch.object(SentiSenseClient, "_get")
    def test_returns_plain_profiles_and_leaves_out_unknown_tickers(self, mock_get, client):
        profile = {"ticker": "EXMP", "name": "Example Corp", "sector": "Technology"}
        mock_get.return_value = _mock_response({"EXMP": profile})

        profiles = client.get_stock_descriptions(["EXMP", "QQZZX"])

        assert profiles == {"EXMP": profile}
        assert isinstance(profiles["EXMP"], dict)
        assert profiles.get("QQZZX") is None


class TestPopularStocks:
    @patch.object(SentiSenseClient, "_get")
    def test_popular_tickers(self, mock_get, client):
        mock_get.return_value = _mock_response(["EXMP", "EXMQ"])
        assert client.get_popular_stocks() == ["EXMP", "EXMQ"]
        mock_get.assert_called_once_with("/api/v1/stocks/popular")

    @patch.object(SentiSenseClient, "_get")
    def test_popular_detailed_rows_parse_like_the_full_list(self, mock_get, client):
        mock_get.return_value = _mock_response(
            [{"ticker": "EXMP", "simpleName": "Example", "companyName": "Example Corp",
              "urlSlug": "Example-Corp", "brandColor": "#123456"}]
        )

        rows = client.get_popular_stocks_detailed()

        mock_get.assert_called_once_with("/api/v1/stocks/popular/detailed")
        assert len(rows) == 1 and isinstance(rows[0], StockDetail)
        assert rows[0].companyName == "Example Corp"
        assert rows[0].name == "Example"

    @patch.object(SentiSenseClient, "_get")
    def test_popular_detailed_empty(self, mock_get, client):
        mock_get.return_value = _mock_response([])
        assert client.get_popular_stocks_detailed() == []


class TestGetStockMetricsBreakdown:
    @patch.object(SentiSenseClient, "_get")
    def test_hits_the_ticker_and_metric_path_with_the_window(self, mock_get, client):
        body = {"ticker": "EXMP", "metricType": "sentiment", "entities": []}
        mock_get.return_value = _mock_response(body)

        result = client.get_stock_metrics_breakdown(
            "EXMP", "sentiment", 1_700_000_000_000, 1_700_600_000_000
        )

        mock_get.assert_called_once_with(
            "/api/v1/stocks/EXMP/metrics/sentiment/breakdown",
            params={"startTime": 1_700_000_000_000, "endTime": 1_700_600_000_000},
        )
        assert result == body

    def test_the_window_is_required(self):
        # The API answers 400 without startTime and endTime, so the method has no
        # default for them.
        params = inspect.signature(SentiSenseClient.get_stock_metrics_breakdown).parameters
        for name in ("start_time", "end_time"):
            assert params[name].default is inspect.Parameter.empty
