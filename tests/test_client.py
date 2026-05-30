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

    @patch.object(SentiSenseClient, "_get")
    def test_get_fundamentals_periods_typed_default_all(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={
            "ticker": "NVDA",
            "periods": [
                {"fiscalPeriod": "Q3", "fiscalYear": "2026", "periodEndDate": "2025-10-26",
                 "filingDate": "2025-11-19", "timeframe": "quarterly"},
                {"fiscalPeriod": "Q2", "fiscalYear": "2026", "periodEndDate": "2025-07-27",
                 "filingDate": "2025-08-27", "timeframe": "quarterly"},
                {"fiscalPeriod": "FY", "fiscalYear": "2025", "periodEndDate": "2025-01-26",
                 "filingDate": "2025-02-26", "timeframe": "annual"},
            ],
        })
        periods = client.get_fundamentals_periods("nvda")
        mock_get.assert_called_once_with(
            "/api/v1/stocks/fundamentals/periods", params={"ticker": "NVDA"}
        )
        # default returns ALL periods (parity with Node getFundamentalsPeriods)
        assert len(periods) == 3
        assert periods[0].fiscalPeriod == "Q3"
        assert periods[0].fiscalYear == "2026"
        assert periods[0].periodEndDate == "2025-10-26"

    @patch.object(SentiSenseClient, "_get")
    def test_get_fundamentals_periods_quarterly_filter(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={
            "ticker": "NVDA",
            "periods": [
                {"fiscalPeriod": "Q3", "fiscalYear": "2026", "periodEndDate": "2025-10-26", "timeframe": "quarterly"},
                {"fiscalPeriod": "FY", "fiscalYear": "2025", "periodEndDate": "2025-01-26", "timeframe": "annual"},
            ],
        })
        periods = client.get_fundamentals_periods("NVDA", timeframe="quarterly")
        assert len(periods) == 1
        assert periods[0].fiscalPeriod == "Q3"

    @patch.object(SentiSenseClient, "_get")
    def test_get_fundamentals_periods_empty(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"ticker": "XYZ", "periods": []})
        assert client.get_fundamentals_periods("XYZ") == []

    @patch.object(SentiSenseClient, "_get")
    def test_get_current_fundamentals(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"ticker": "AAPL", "revenue": 1234})
        result = client.get_current_fundamentals("AAPL")
        mock_get.assert_called_once_with(
            "/api/v1/stocks/fundamentals/current", params={"ticker": "AAPL"}
        )
        assert result["revenue"] == 1234

    @patch.object(SentiSenseClient, "_get")
    def test_get_historical_revenue(self, mock_get, client):
        mock_get.return_value = _mock_response(
            json_data={"ticker": "AAPL", "revenue": [{"fiscalYear": 2024, "value": 1000}]}
        )
        result = client.get_historical_revenue("AAPL")
        mock_get.assert_called_once_with(
            "/api/v1/stocks/fundamentals/historical/revenue", params={"ticker": "AAPL"}
        )
        assert result["revenue"][0]["fiscalYear"] == 2024

    @patch.object(SentiSenseClient, "_get")
    def test_get_short_interest(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"ticker": "GME", "shortInterest": 12345})
        result = client.get_short_interest("GME")
        mock_get.assert_called_once_with(
            "/api/v1/stocks/short-interest", params={"ticker": "GME"}
        )
        assert result["shortInterest"] == 12345

    @patch.object(SentiSenseClient, "_get")
    def test_get_float(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"ticker": "AAPL", "float": 15000000000})
        result = client.get_float("AAPL")
        mock_get.assert_called_once_with("/api/v1/stocks/float", params={"ticker": "AAPL"})
        assert result["float"] == 15000000000

    @patch.object(SentiSenseClient, "_get")
    def test_get_short_volume(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"ticker": "AAPL", "shortVolume": 500000})
        result = client.get_short_volume("AAPL")
        mock_get.assert_called_once_with(
            "/api/v1/stocks/short-volume", params={"ticker": "AAPL"}
        )
        assert result["shortVolume"] == 500000


class TestKbEndpoints:
    @patch.object(SentiSenseClient, "_get")
    def test_get_popular_kb_entities(self, mock_get, client):
        mock_get.return_value = _mock_response(
            json_data=[{"entityId": "kb/company/1", "name": "Apple Inc."}]
        )
        result = client.get_popular_kb_entities()
        mock_get.assert_called_once_with("/api/v1/kb/entities/popular")
        assert result[0]["entityId"] == "kb/company/1"

    @patch.object(SentiSenseClient, "_get")
    def test_get_kb_entity(self, mock_get, client):
        mock_get.return_value = _mock_response(
            json_data={"entityId": "kb/company/1", "name": "Apple Inc.", "type": "company"}
        )
        result = client.get_kb_entity("kb/company/1")
        mock_get.assert_called_once_with("/api/v1/kb/entities/kb/company/1")
        assert result["type"] == "company"

    @patch.object(SentiSenseClient, "_get")
    def test_get_all_kb_entities(self, mock_get, client):
        mock_get.return_value = _mock_response(
            json_data=[
                {"entityId": "kb/company/1", "name": "Apple Inc."},
                {"entityId": "kb/person/2", "name": "Tim Cook"},
            ]
        )
        result = client.get_all_kb_entities()
        mock_get.assert_called_once_with("/api/v1/kb/entities/all")
        assert len(result) == 2
        assert result[1]["name"] == "Tim Cook"


class TestKpiEndpoints:
    @patch.object(SentiSenseClient, "_get")
    def test_get_company_kpis_returns_typed(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={
            "isPreview": False,
            "previewReason": None,
            "data": {
                "ticker": "AAPL",
                "companyName": "Apple Inc.",
                "cik": "0000320193",
                "lastUpdated": "2026-04-30",
                "kpis": [
                    {
                        "id": "iphone_revenue",
                        "name": "iPhone Revenue",
                        "category": "product_revenue",
                        "unit": "USD",
                        "displayFormat": "currency_abbreviated",
                        "chartType": "bar",
                        "values": [
                            {"period": "Q2 FY2026", "date": "2025-12-27", "value": 85269000000.0, "isEstimate": None}
                        ],
                        "sourceRef": "Apple 8-K Q2 FY2026",
                        "discontinued": False,
                        "discontinuedNote": None,
                    }
                ],
            },
        })
        result = client.get_company_kpis("AAPL")
        mock_get.assert_called_once_with("/api/v1/stocks/AAPL/kpis")
        # PreviewResult proxies attribute access to the typed CompanyKpis
        assert result.is_preview is False
        assert result.ticker == "AAPL"
        assert result.kpis[0].id == "iphone_revenue"
        assert result.kpis[0].values[0].value == 85269000000.0

    @patch.object(SentiSenseClient, "_get")
    def test_list_kpi_coverage_returns_typed(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={
            "count": 2,
            "tickers": [
                {"ticker": "AAPL", "companyName": "Apple Inc.", "lastUpdated": "2026-04-30", "kpiCount": 8},
                {"ticker": "TSLA", "companyName": "Tesla, Inc.", "lastUpdated": "2026-04-15", "kpiCount": 6},
            ],
        })
        coverage = client.list_kpi_coverage()
        mock_get.assert_called_once_with("/api/v1/stocks/with-kpis")
        assert coverage.count == 2
        assert coverage.tickers[0].ticker == "AAPL"
        assert coverage.tickers[0].kpiCount == 8

    @patch.object(SentiSenseClient, "_get")
    def test_get_kpi_types_returns_typed_list(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[
            {"id": "iphone_revenue", "name": "iPhone Revenue", "category": "product_revenue", "chartType": "bar"},
            {"id": "services_revenue", "name": "Services Revenue", "category": "segment_revenue", "chartType": "line"},
        ])
        types = client.get_kpi_types("aapl")
        mock_get.assert_called_once_with("/api/v1/stocks/AAPL/kpis/types")
        assert len(types) == 2
        assert types[0].id == "iphone_revenue"
        assert types[1].chartType == "line"


class TestInstitutionalEndpoints:
    @patch.object(SentiSenseClient, "_get")
    def test_get_institutional_quarters(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=["2025-12-31"])
        result = client.get_institutional_quarters()
        mock_get.assert_called_once_with("/api/v1/institutional/quarters")
        assert result == ["2025-12-31"]

    @patch.object(SentiSenseClient, "_get")
    def test_get_institutional_flows(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"inflows": [], "outflows": []})
        result = client.get_institutional_flows("2025-12-31", limit=10)
        mock_get.assert_called_once_with(
            "/api/v1/institutional/flows",
            params={"reportDate": "2025-12-31", "limit": 10},
        )
        assert "inflows" in result
        assert "outflows" in result

    @patch.object(SentiSenseClient, "_get")
    def test_get_stock_holders(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[])
        client.get_stock_holders("AAPL", "2025-12-31")
        mock_get.assert_called_once_with(
            "/api/v1/institutional/holders/AAPL",
            params={"reportDate": "2025-12-31"},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_get_activist_positions(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[])
        client.get_activist_positions("2025-12-31")
        mock_get.assert_called_once_with(
            "/api/v1/institutional/activist",
            params={"reportDate": "2025-12-31"},
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


class TestMetricsV2Endpoints:
    @patch.object(SentiSenseClient, "_get")
    def test_get_metrics_defaults(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[{"timestamp": 1700000000000, "value": 5}])
        result = client.get_metrics("AAPL")
        mock_get.assert_called_once_with(
            "/api/v2/metrics/entity/AAPL/metric/mentions",
            params={},
        )
        assert result == [{"timestamp": 1700000000000, "value": 5}]

    @patch.object(SentiSenseClient, "_get")
    def test_get_metrics_with_all_params(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[])
        client.get_metrics(
            "TSLA",
            metric_type="sentiment",
            start_time=1700000000000,
            end_time=1700100000000,
            max_data_points=50,
        )
        mock_get.assert_called_once_with(
            "/api/v2/metrics/entity/TSLA/metric/sentiment",
            params={"startTime": 1700000000000, "endTime": 1700100000000, "maxDataPoints": 50},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_get_metrics_sentisense_score(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[])
        client.get_metrics("NVDA", metric_type="sentisense_score")
        mock_get.assert_called_once_with(
            "/api/v2/metrics/entity/NVDA/metric/sentisense_score",
            params={},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_get_metrics_distribution_defaults(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"news": 10, "reddit": 5})
        result = client.get_metrics_distribution("AAPL")
        mock_get.assert_called_once_with(
            "/api/v2/metrics/entity/AAPL/distribution/mentions",
            params={"dimension": "source"},
        )
        assert result == {"news": 10, "reddit": 5}

    @patch.object(SentiSenseClient, "_get")
    def test_get_metrics_distribution_with_time_range(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={})
        client.get_metrics_distribution(
            "MSFT",
            metric_type="sentiment",
            dimension="source",
            start_time=1700000000000,
            end_time=1700100000000,
        )
        mock_get.assert_called_once_with(
            "/api/v2/metrics/entity/MSFT/distribution/sentiment",
            params={"dimension": "source", "startTime": 1700000000000, "endTime": 1700100000000},
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
