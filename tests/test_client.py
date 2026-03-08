"""Unit tests for SentiSenseClient."""

import json
from unittest.mock import MagicMock, patch

import pytest

from sentisense import (
    SentiSenseClient,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    APIError,
    __version__,
)


@pytest.fixture
def client():
    return SentiSenseClient("test-api-key")


def _mock_response(status_code=200, json_data=None, reason="OK"):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.reason = reason
    resp.json.return_value = json_data or {}
    return resp


class TestClientConstruction:
    def test_default_base_url(self, client):
        assert client.base_url == "https://app.sentisense.ai"

    def test_custom_base_url(self):
        c = SentiSenseClient("key", base_url="https://custom.example.com/")
        assert c.base_url == "https://custom.example.com"

    def test_api_key_header(self, client):
        assert client.session.headers["X-SentiSense-API-Key"] == "test-api-key"

    def test_user_agent_header(self, client):
        assert client.session.headers["User-Agent"] == f"sentisense-python/{__version__}"

    def test_default_timeout(self, client):
        assert client.timeout == 30.0

    def test_custom_timeout(self):
        c = SentiSenseClient("key", timeout=10.0)
        assert c.timeout == 10.0


class TestStockEndpoints:
    @patch.object(SentiSenseClient, "_get")
    def test_get_stock_price(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"price": 150.0})
        result = client.get_stock_price("AAPL")
        mock_get.assert_called_once_with("/api/v1/stocks/price", params={"ticker": "AAPL"})
        assert result == {"price": 150.0}

    @patch.object(SentiSenseClient, "_get")
    def test_get_stock_prices(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[{"ticker": "AAPL"}, {"ticker": "MSFT"}])
        result = client.get_stock_prices(["AAPL", "MSFT"])
        mock_get.assert_called_once_with("/api/v1/stocks/prices", params={"tickers": "AAPL,MSFT"})
        assert len(result) == 2

    @patch.object(SentiSenseClient, "_get")
    def test_get_stock_profile(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"name": "Apple Inc."})
        result = client.get_stock_profile("AAPL")
        mock_get.assert_called_once_with("/api/v1/stocks/AAPL/profile")
        assert result["name"] == "Apple Inc."

    @patch.object(SentiSenseClient, "_get")
    def test_get_stock_chart(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"candles": []})
        client.get_stock_chart("AAPL", timeframe="1W")
        mock_get.assert_called_once_with(
            "/api/v1/stocks/chart", params={"ticker": "AAPL", "timeframe": "1W"}
        )

    @patch.object(SentiSenseClient, "_get")
    def test_get_all_stocks(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=["AAPL", "MSFT"])
        result = client.get_all_stocks()
        mock_get.assert_called_once_with("/api/v1/stocks")
        assert result == ["AAPL", "MSFT"]

    @patch.object(SentiSenseClient, "_get")
    def test_get_market_status(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"status": "open"})
        result = client.get_market_status()
        mock_get.assert_called_once_with("/api/v1/stocks/market-status")
        assert result["status"] == "open"

    @patch.object(SentiSenseClient, "_get")
    def test_get_fundamentals_with_filters(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={})
        client.get_fundamentals("AAPL", timeframe="annual", fiscal_period="Q1", fiscal_year=2025)
        mock_get.assert_called_once_with(
            "/api/v1/stocks/fundamentals",
            params={"ticker": "AAPL", "timeframe": "annual", "fiscalPeriod": "Q1", "fiscalYear": 2025},
        )


class TestInstitutionalEndpoints:
    @patch.object(SentiSenseClient, "_get")
    def test_get_institutional_quarters(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=["2025-03-31"])
        result = client.get_institutional_quarters()
        mock_get.assert_called_once_with("/api/v1/institutional/quarters")
        assert result == ["2025-03-31"]

    @patch.object(SentiSenseClient, "_get")
    def test_get_institutional_flows(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"inflows": [], "outflows": []})
        result = client.get_institutional_flows("2025-03-31", limit=10)
        mock_get.assert_called_once_with(
            "/api/v1/institutional/flows",
            params={"reportDate": "2025-03-31", "limit": 10},
        )
        assert "inflows" in result
        assert "outflows" in result

    @patch.object(SentiSenseClient, "_get")
    def test_get_stock_holders(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[])
        client.get_stock_holders("AAPL", "2025-03-31")
        mock_get.assert_called_once_with(
            "/api/v1/institutional/holders/AAPL",
            params={"reportDate": "2025-03-31"},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_get_activist_positions(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[])
        client.get_activist_positions("2025-03-31")
        mock_get.assert_called_once_with(
            "/api/v1/institutional/activist",
            params={"reportDate": "2025-03-31"},
        )


class TestDocumentEndpoints:
    @patch.object(SentiSenseClient, "_get")
    def test_get_documents_by_ticker(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[{"id": "doc1"}])
        result = client.get_documents_by_ticker("AAPL", source="news", days=7, limit=10)
        mock_get.assert_called_once_with(
            "/api/v1/documents/ticker/AAPL",
            params={"source": "news", "days": 7, "limit": 10},
        )
        assert result == [{"id": "doc1"}]

    @patch.object(SentiSenseClient, "_get")
    def test_get_documents_by_ticker_range(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[])
        client.get_documents_by_ticker_range("AAPL", "2025-01-01", "2025-01-31")
        mock_get.assert_called_once_with(
            "/api/v1/documents/ticker/AAPL/range",
            params={"startDate": "2025-01-01", "endDate": "2025-01-31"},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_search_documents(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[{"id": "doc1"}])
        result = client.search_documents("AI earnings", source="reddit", limit=5)
        mock_get.assert_called_once_with(
            "/api/v1/documents/search",
            params={"query": "AI earnings", "source": "reddit", "limit": 5},
        )
        assert len(result) == 1

    @patch.object(SentiSenseClient, "_get")
    def test_get_documents_by_source(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[])
        client.get_documents_by_source("x", hours=24)
        mock_get.assert_called_once_with(
            "/api/v1/documents/source/x",
            params={"hours": 24},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_get_stories(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[{"cluster": {}}])
        client.get_stories(limit=5, expanded=True)
        mock_get.assert_called_once_with(
            "/api/v1/documents/stories",
            params={"limit": 5, "expanded": True},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_get_story(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"cluster": {"id": "abc"}})
        result = client.get_story("abc")
        mock_get.assert_called_once_with("/api/v1/documents/stories/abc")
        assert result["cluster"]["id"] == "abc"

    @patch.object(SentiSenseClient, "_get")
    def test_get_stories_by_ticker(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[])
        client.get_stories_by_ticker("TSLA", limit=3)
        mock_get.assert_called_once_with(
            "/api/v1/documents/stories/ticker/TSLA",
            params={"limit": 3},
        )


class TestEntityMetricsEndpoints:
    @patch.object(SentiSenseClient, "_get")
    def test_get_mentions(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"data": []})
        client.get_mentions("AAPL", source="reddit", start_date="2025-01-01")
        mock_get.assert_called_once_with(
            "/api/v1/entity-metrics/stocks/AAPL/mentions",
            params={"source": "reddit", "startDate": "2025-01-01"},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_get_mention_count(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"count": 42})
        result = client.get_mention_count("AAPL")
        mock_get.assert_called_once_with(
            "/api/v1/entity-metrics/stocks/AAPL/mentions/count",
            params={},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_get_mention_count_by_source(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={})
        client.get_mention_count_by_source("TSLA", start_date="2025-01-01", end_date="2025-01-31")
        mock_get.assert_called_once_with(
            "/api/v1/entity-metrics/stocks/TSLA/mentions/count/by-source",
            params={"startDate": "2025-01-01", "endDate": "2025-01-31"},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_get_sentiment(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"sentiment": 0.75})
        result = client.get_sentiment("AAPL")
        mock_get.assert_called_once_with(
            "/api/v1/entity-metrics/stocks/AAPL/sentiment",
            params={},
        )
        assert result["sentiment"] == 0.75

    @patch.object(SentiSenseClient, "_get")
    def test_get_sentiment_by_source(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={})
        client.get_sentiment_by_source("AAPL", date="2025-01-15")
        mock_get.assert_called_once_with(
            "/api/v1/entity-metrics/stocks/AAPL/sentiment/by-source",
            params={"date": "2025-01-15"},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_get_average_sentiment(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={})
        client.get_average_sentiment("NVDA", start_date="2025-01-01", end_date="2025-03-01")
        mock_get.assert_called_once_with(
            "/api/v1/entity-metrics/stocks/NVDA/sentiment/average",
            params={"startDate": "2025-01-01", "endDate": "2025-03-01"},
        )


class TestErrorHandling:
    def test_401_raises_authentication_error(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(401, {"message": "Invalid API key"}, "Unauthorized")):
            with pytest.raises(AuthenticationError) as exc_info:
                client.get_stock_price("AAPL")
            assert exc_info.value.status_code == 401
            assert "Invalid API key" in exc_info.value.message

    def test_403_raises_authentication_error(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(403, {}, "Forbidden")):
            with pytest.raises(AuthenticationError) as exc_info:
                client.get_stock_price("AAPL")
            assert exc_info.value.status_code == 403

    def test_404_raises_not_found_error(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(404, {}, "Not Found")):
            with pytest.raises(NotFoundError):
                client.get_stock_profile("INVALID")

    def test_429_raises_rate_limit_error(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(429, {"message": "Rate limit exceeded"}, "Too Many Requests")):
            with pytest.raises(RateLimitError) as exc_info:
                client.get_all_stocks()
            assert "Rate limit exceeded" in exc_info.value.message

    def test_500_raises_api_error(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(500, {}, "Internal Server Error")):
            with pytest.raises(APIError) as exc_info:
                client.get_market_status()
            assert exc_info.value.status_code == 500
