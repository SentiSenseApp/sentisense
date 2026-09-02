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
        mock_get.return_value = _mock_response(json_data={"ticker": "AAPL", "currentPrice": 150.0})
        result = client.get_stock_price("AAPL")
        mock_get.assert_called_once_with("/api/v1/stocks/price", params={"ticker": "AAPL"})
        assert result.currentPrice == 150.0
        assert result["ticker"] == "AAPL"

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
    def test_get_all_stocks_detailed_carries_company_names(self, mock_get, client):
        mock_get.return_value = _mock_response(
            json_data=[
                {
                    "ticker": "A",
                    "simpleName": "Agilent",
                    "companyName": "Agilent Technologies, Inc.",
                    "kbEntityId": "kb/company/107",
                    "urlSlug": "Agilent-Technologies-Inc",
                    "socialDominance": {"value": 0.0005, "rank": 451},
                }
            ]
        )
        result = client.get_all_stocks_detailed()
        mock_get.assert_called_once_with("/api/v1/stocks/detailed")
        assert result[0].simpleName == "Agilent"
        assert result[0].companyName == "Agilent Technologies, Inc."
        # The API never sends "name"; the legacy alias falls back to simpleName
        # rather than staying an empty string.
        assert result[0].name == "Agilent"
        assert result[0].socialDominance["rank"] == 451

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

    def test_get_all_kb_entities_removed(self, client):
        assert not hasattr(client, "get_all_kb_entities")

    @patch.object(SentiSenseClient, "_get")
    def test_get_stock_entities(self, mock_get, client):
        mock_get.return_value = _mock_response(
            json_data=[
                {"entityId": "kb/person/1", "name": "Tim Cook", "type": "PERSON"},
                {"entityId": "kb/product/3", "name": "iPhone", "type": "PRODUCT"},
            ]
        )
        result = client.get_stock_entities("AAPL")
        mock_get.assert_called_once_with("/api/v1/stocks/AAPL/entities")
        assert len(result) == 2
        assert result[1]["name"] == "iPhone"

    @patch.object(SentiSenseClient, "_get")
    def test_get_stock_ai_summary_defaults_to_basic(self, mock_get, client):
        mock_get.return_value = _mock_response(
            json_data={
                "ticker": "AAPL",
                "status": "READY",
                "reportType": "SUMMARY",
                "sectionOrder": ["Executive Summary"],
            }
        )
        result = client.get_stock_ai_summary("AAPL")
        mock_get.assert_called_once_with(
            "/api/v1/stocks/AAPL/ai-summary", params={"depth": "basic"}
        )
        assert result["reportType"] == "SUMMARY"

    @patch.object(SentiSenseClient, "_get")
    def test_get_stock_ai_summary_deep(self, mock_get, client):
        mock_get.return_value = _mock_response(
            json_data={
                "ticker": "AAPL",
                "status": "READY",
                "reportType": "FULL",
                "moatRating": 8,
                "aiDisruptionRisk": "Low",
            }
        )
        result = client.get_stock_ai_summary("AAPL", depth="deep")
        mock_get.assert_called_once_with(
            "/api/v1/stocks/AAPL/ai-summary", params={"depth": "deep"}
        )
        assert result["moatRating"] == 8

    @patch.object(SentiSenseClient, "_get")
    def test_get_stock_ai_summary_sends_no_force_refresh(self, mock_get, client):
        # The endpoint accepts a forceRefresh flag that does not change the report a
        # caller receives. It is deliberately not exposed and never sent.
        mock_get.return_value = _mock_response(json_data={"ticker": "AAPL"})
        client.get_stock_ai_summary("AAPL", depth="deep")
        _, kwargs = mock_get.call_args
        assert "forceRefresh" not in kwargs["params"]


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
        mock_get.return_value = _mock_response(
            json_data=[{"value": "2025Q4", "label": "Q4 2025", "reportDate": "2025-12-31", "pending": False}]
        )
        result = client.get_institutional_quarters()
        mock_get.assert_called_once_with("/api/v1/institutional/quarters")
        assert result[0].reportDate == "2025-12-31"
        assert result[0].value == "2025Q4"

    @patch.object(SentiSenseClient, "_get")
    def test_get_institutional_flows(self, mock_get, client):
        mock_get.return_value = _mock_response(
            json_data={"isPreview": False, "previewReason": None, "data": {"inflows": [], "outflows": []}}
        )
        result = client.get_institutional_flows("2025-12-31", limit=10)
        mock_get.assert_called_once_with(
            "/api/v1/institutional/flows",
            params={"reportDate": "2025-12-31", "limit": 10},
        )
        assert result.is_preview is False
        assert result.inflows == []
        assert result.outflows == []

    @patch.object(SentiSenseClient, "_get")
    def test_get_institutional_flows_omitted_report_date(self, mock_get, client):
        # Omitting report_date should not send reportDate; the server defaults to the
        # latest quarter and labels a partial one via the coverage fields.
        mock_get.return_value = _mock_response(
            json_data={
                "isPreview": False,
                "previewReason": None,
                "data": {
                    "inflows": [],
                    "outflows": [],
                    "reportDate": "2026-06-30",
                    "isPending": True,
                    "filerCount": 578,
                    "baselineFilerCount": 8789,
                },
            }
        )
        result = client.get_institutional_flows()
        mock_get.assert_called_once_with(
            "/api/v1/institutional/flows",
            params={"limit": 50},
        )
        assert result.reportDate == "2026-06-30"
        assert result.isPending is True
        assert result.filerCount == 578
        assert result.baselineFilerCount == 8789

    @patch.object(SentiSenseClient, "_get")
    def test_get_stock_holders(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[])
        client.get_stock_holders("AAPL", "2025-12-31")
        mock_get.assert_called_once_with(
            "/api/v1/institutional/holders/AAPL",
            params={"reportDate": "2025-12-31"},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_get_stock_holders_paging_params(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[])
        client.get_stock_holders(
            "AAPL",
            "2025-12-31",
            limit=5,
            offset=10,
            sort_by="valueUsd",
            sort_dir="asc",
        )
        mock_get.assert_called_once_with(
            "/api/v1/institutional/holders/AAPL",
            params={
                "reportDate": "2025-12-31",
                "limit": 5,
                "offset": 10,
                "sortBy": "valueUsd",
                "sortDir": "asc",
            },
        )

    @patch.object(SentiSenseClient, "_get")
    def test_get_stock_holders_partial_paging_params(self, mock_get, client):
        # Only the arguments actually supplied are sent, so the server keeps applying
        # its own defaults for the rest instead of receiving nulls.
        mock_get.return_value = _mock_response(json_data=[])
        client.get_stock_holders("AAPL", "2025-12-31", limit=25)
        mock_get.assert_called_once_with(
            "/api/v1/institutional/holders/AAPL",
            params={"reportDate": "2025-12-31", "limit": 25},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_get_stock_holders_offset_zero_is_sent(self, mock_get, client):
        # offset=0 is a real value, not "unset": it must survive the None check.
        mock_get.return_value = _mock_response(json_data=[])
        client.get_stock_holders("AAPL", "2025-12-31", limit=5, offset=0)
        mock_get.assert_called_once_with(
            "/api/v1/institutional/holders/AAPL",
            params={"reportDate": "2025-12-31", "limit": 5, "offset": 0},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_get_stock_holders_paged_response_unwraps(self, mock_get, client):
        # A paged response carries the paging metadata next to the rows.
        mock_get.return_value = _mock_response(
            json_data={
                "isPreview": False,
                "previewReason": None,
                "totalCount": 6044,
                "data": {
                    "ticker": "AAPL",
                    "holderCount": 6044,
                    "returnedCount": 2,
                    "offset": 0,
                    "holders": [{"filerName": "A"}, {"filerName": "B"}],
                },
            }
        )
        result = client.get_stock_holders("AAPL", "2025-12-31", limit=2)
        assert result.is_preview is False
        assert result.returnedCount == 2
        assert result.offset == 0
        assert len(result.holders) == 2

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
        mock_get.return_value = _mock_response(
            json_data={"documents": [{"id": "doc1"}], "totalCount": 1, "searchTicker": "AAPL"}
        )
        result = client.get_documents_by_ticker("AAPL", source="news", days=7, limit=10)
        mock_get.assert_called_once_with(
            "/api/v1/documents/ticker/AAPL",
            params={"source": "news", "days": 7, "limit": 10},
        )
        assert result.totalCount == 1
        assert result.documents[0].id == "doc1"

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
        mock_get.return_value = _mock_response(json_data={"documents": [{"id": "doc1"}], "totalCount": 1})
        result = client.search_documents("AI earnings", source="reddit", limit=5)
        mock_get.assert_called_once_with(
            "/api/v1/documents/search",
            params={"query": "AI earnings", "source": "reddit", "limit": 5},
        )
        assert len(result.documents) == 1

    @patch.object(SentiSenseClient, "_get")
    def test_get_documents_by_source(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"documents": []})
        client.get_documents_by_source("x", hours=24)
        mock_get.assert_called_once_with(
            "/api/v1/documents/source/x",
            params={"hours": 24},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_get_documents_by_source_sort(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"documents": []})
        client.get_documents_by_source("news", hours=6, limit=50, sort="top")
        mock_get.assert_called_once_with(
            "/api/v1/documents/source/news",
            params={"hours": 6, "limit": 50, "sort": "top"},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_get_stories(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[{"cluster": {"id": "c1"}}])
        client.get_stories(limit=5)
        mock_get.assert_called_once_with(
            "/api/v1/documents/stories",
            params={"limit": 5},
        )

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
            "/api/v2/metrics/entity/AAPL/metric/sentiment",
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


class TestCalendarEndpoints:
    """Calendar API: earnings calendar, preview-gated by window."""

    _SAMPLE = {
        "isPreview": True,
        "previewReason": "PRO_REQUIRED",
        "totalCount": 42,
        "data": {
            "earnings": [
                {
                    "ticker": "AAPL",
                    "companyName": "Apple Inc.",
                    "earningsDate": "2026-04-30",
                    "earningsTime": "after_close",
                    "fiscalQuarter": "Q2 2026",
                    "confirmed": True,
                    "estimatedEps": 1.62,
                    "source": "provider+web",
                }
            ],
            "metadata": {
                "generatedAt": 1776528000,
                "windowStart": "2026-04-20",
                "windowEnd": "2026-05-20",
                "count": 1,
                "source": "sentisense",
            },
        },
    }

    @patch.object(SentiSenseClient, "_get")
    def test_get_earnings_calendar_unwraps_and_types(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=self._SAMPLE)

        cal = client.get_earnings_calendar()

        mock_get.assert_called_once_with("/api/v1/calendar/earnings", params={})
        assert cal.is_preview is True
        assert cal.preview_reason == "PRO_REQUIRED"
        assert cal.total_count == 42
        # attribute + dict access on the typed event
        e = cal.earnings[0]
        assert e.ticker == "AAPL"
        assert e.earningsDate == "2026-04-30"
        assert e["earningsTime"] == "after_close"
        assert e.estimatedEps == 1.62
        # internal provider attribution must not survive into the typed model
        assert not hasattr(e, "source")
        assert cal.metadata.windowStart == "2026-04-20"
        assert cal.metadata.generatedAt == 1776528000

    @patch.object(SentiSenseClient, "_get")
    def test_get_earnings_calendar_passes_filters(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=self._SAMPLE)

        client.get_earnings_calendar(
            ticker="aapl", week="next", date_from="2026-05-01",
            date_to="2026-05-31", confirmed=True, time="before_open",
        )

        mock_get.assert_called_once_with(
            "/api/v1/calendar/earnings",
            params={
                "ticker": "AAPL",
                "week": "next",
                "from": "2026-05-01",
                "to": "2026-05-31",
                "confirmed": True,
                "time": "before_open",
            },
        )


class TestRetryAfterParsing:
    """`Retry-After` is attacker- and vendor-controlled input, not a trusted number.

    Two shapes have to be safe: a value large enough to strand a synchronous caller, and a
    value that is not a number at all (the header may legally carry an HTTP-date). Before
    the clamp, the first slept for the full duration and the second raised ValueError out
    of the 429 path.
    """

    def test_absent_header_uses_default(self):
        from sentisense.client import _retry_after_seconds

        resp = MagicMock()
        resp.headers = {}
        assert _retry_after_seconds(resp, default=7.0) == 7.0

    def test_numeric_value_is_honoured(self):
        from sentisense.client import _retry_after_seconds

        resp = MagicMock()
        resp.headers = {"Retry-After": "5"}
        assert _retry_after_seconds(resp) == 5.0

    def test_oversized_value_is_capped(self):
        from sentisense.client import _retry_after_seconds, _MAX_DEEP_HISTORY_WAIT

        resp = MagicMock()
        resp.headers = {"Retry-After": "86400"}
        assert _retry_after_seconds(resp) == _MAX_DEEP_HISTORY_WAIT

    def test_rate_limit_gets_the_longer_ceiling(self):
        from sentisense.client import _retry_after_seconds, _MAX_RATE_LIMIT_WAIT

        resp = MagicMock()
        resp.headers = {"Retry-After": "86400"}
        got = _retry_after_seconds(resp, default=60.0, max_wait=_MAX_RATE_LIMIT_WAIT)
        assert got == _MAX_RATE_LIMIT_WAIT

    def test_http_date_falls_back_instead_of_raising(self):
        from sentisense.client import _retry_after_seconds

        resp = MagicMock()
        resp.headers = {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}
        assert _retry_after_seconds(resp, default=3.0) == 3.0

    @pytest.mark.parametrize("raw", ["nan", "inf", "-inf"])
    def test_non_finite_values_fall_back(self, raw):
        from sentisense.client import _retry_after_seconds

        resp = MagicMock()
        resp.headers = {"Retry-After": raw}
        assert _retry_after_seconds(resp, default=3.0) == 3.0

    def test_negative_value_still_waits_a_little(self):
        from sentisense.client import _retry_after_seconds

        resp = MagicMock()
        resp.headers = {"Retry-After": "-10"}
        assert _retry_after_seconds(resp) == 0.5


class TestGetStockSentiment:
    def test_calls_the_sentiment_path_and_unwraps(self, client):
        payload = {
            "isPreview": False,
            "previewReason": None,
            "data": {
                "ticker": "AAPL",
                "sentisenseScore": 41.2,
                "direction": "Bullish",
                "bySource": [{"source": "news", "direction": "Bullish", "mentionShare": 0.5}],
            },
        }
        with patch.object(client.session, "request", return_value=_mock_response(json_data=payload)) as req:
            result = client.get_stock_sentiment("AAPL")

        assert "/api/v1/stocks/AAPL/sentiment" in req.call_args[0][1]
        assert result.is_preview is False
        assert result["ticker"] == "AAPL"
        assert result["direction"] == "Bullish"

    def test_preview_flag_is_surfaced(self, client):
        payload = {"isPreview": True, "previewReason": "PRO_REQUIRED", "data": {"ticker": "AAPL"}}
        with patch.object(client.session, "request", return_value=_mock_response(json_data=payload)):
            result = client.get_stock_sentiment("AAPL")

        assert result.is_preview is True
        assert result.preview_reason == "PRO_REQUIRED"


class TestPoliticianDirectory:
    """The directory is how a caller finds member slugs, including for former members.

    ``get_politician_members()`` cannot serve that purpose: it is tier-gated and it omits
    members who have left Congress, so without this a former member is reachable only by a
    slug that no endpoint hands out.
    """

    @patch.object(SentiSenseClient, "_get")
    def test_defaults_send_paging_only(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"data": {"members": [], "totalCount": 0}})
        client.get_politician_directory()
        mock_get.assert_called_once_with(
            "/api/v1/politicians/directory",
            params={"limit": 50, "offset": 0},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_query_reaches_the_wire(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"data": {"members": [], "totalCount": 0}})
        client.get_politician_directory(q="pelosi", limit=5, offset=10)
        mock_get.assert_called_once_with(
            "/api/v1/politicians/directory",
            params={"limit": 5, "offset": 10, "q": "pelosi"},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_unwraps_the_data_envelope(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={
            "data": {
                "members": [{"urlSlug": "Kelly-Loeffler", "displayName": "Kelly Loeffler",
                             "former": True, "servedUntil": "2021"}],
                "totalCount": 1,
            },
        })
        result = client.get_politician_directory(q="loeffler")

        assert result["totalCount"] == 1
        assert result["members"][0]["urlSlug"] == "Kelly-Loeffler"
        # The former flag is the reason this endpoint exists; dropping it in unwrapping
        # would leave callers unable to tell a sitting member from one who left.
        assert result["members"][0]["former"] is True
        assert result["members"][0]["servedUntil"] == "2021"

    @patch.object(SentiSenseClient, "_get")
    def test_tolerates_a_response_without_the_envelope(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"members": [], "totalCount": 0})
        assert client.get_politician_directory() == {"members": [], "totalCount": 0}


class TestPoliticianActivityPaging:
    """The activity window holds thousands of rows but answers one page at a time.

    Without ``limit`` / ``offset`` a caller can only ever see the first page, so the
    arguments have to reach the wire, and omitting them has to keep producing exactly
    the request the SDK sent before they existed.
    """

    @patch.object(SentiSenseClient, "_get")
    def test_omitting_both_sends_the_original_request(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[])
        client.get_politician_activity()
        mock_get.assert_called_once_with(
            "/api/v1/politicians/activity",
            params={"lookbackDays": 90},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_omitting_both_with_explicit_lookback(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[])
        client.get_politician_activity(365)
        mock_get.assert_called_once_with(
            "/api/v1/politicians/activity",
            params={"lookbackDays": 365},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_limit_and_offset_are_sent(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[])
        client.get_politician_activity(365, limit=500, offset=500)
        mock_get.assert_called_once_with(
            "/api/v1/politicians/activity",
            params={"lookbackDays": 365, "limit": 500, "offset": 500},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_limit_alone_leaves_offset_to_the_server(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data=[])
        client.get_politician_activity(limit=25)
        mock_get.assert_called_once_with(
            "/api/v1/politicians/activity",
            params={"lookbackDays": 90, "limit": 25},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_offset_zero_is_sent(self, mock_get, client):
        # offset=0 is a real value, not "unset": it must survive the None check.
        mock_get.return_value = _mock_response(json_data=[])
        client.get_politician_activity(limit=5, offset=0)
        mock_get.assert_called_once_with(
            "/api/v1/politicians/activity",
            params={"lookbackDays": 90, "limit": 5, "offset": 0},
        )

    def test_paging_arguments_are_keyword_only(self, client):
        with pytest.raises(TypeError):
            client.get_politician_activity(365, 500)  # type: ignore[misc]

    @patch.object(SentiSenseClient, "_get")
    def test_total_count_sizes_the_window(self, mock_get, client):
        mock_get.return_value = _mock_response(
            json_data={
                "isPreview": False,
                "previewReason": None,
                "totalCount": 6586,
                "data": [
                    {"ticker": "MPC", "transactionType": "purchase"},
                    {"ticker": "NOW", "transactionType": "sale"},
                ],
            }
        )
        result = client.get_politician_activity(365, limit=2)
        assert result.total_count == 6586
        assert len(result) == 2
        assert result[0].ticker == "MPC"


class TestPoliticianMemberPaging:
    """A member's history is one page, not the whole thing.

    Most members arrive complete in the default page, so the arguments have to be
    optional and omitting them has to keep producing exactly the request the SDK sent
    before they existed. A handful of members have thousands of disclosures, so the
    arguments also have to actually reach the wire.
    """

    @patch.object(SentiSenseClient, "_get")
    def test_omitting_both_sends_the_original_request(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={})
        client.get_politician_member("Nancy-Pelosi")
        mock_get.assert_called_once_with(
            "/api/v1/politicians/member/Nancy-Pelosi",
            params={},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_limit_and_offset_are_sent(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={})
        client.get_politician_member("Ro-Khanna", limit=500, offset=500)
        mock_get.assert_called_once_with(
            "/api/v1/politicians/member/Ro-Khanna",
            params={"limit": 500, "offset": 500},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_offset_zero_is_sent(self, mock_get, client):
        # offset=0 is a real value, not "unset": it must survive the None check.
        mock_get.return_value = _mock_response(json_data={})
        client.get_politician_member("Ro-Khanna", limit=5, offset=0)
        mock_get.assert_called_once_with(
            "/api/v1/politicians/member/Ro-Khanna",
            params={"limit": 5, "offset": 0},
        )

    def test_paging_arguments_are_keyword_only(self, client):
        with pytest.raises(TypeError):
            client.get_politician_member("Ro-Khanna", 500)  # type: ignore[misc]

    @patch.object(SentiSenseClient, "_get")
    def test_total_count_sizes_the_history_and_profile_does_not_shrink(
        self, mock_get, client
    ):
        # The page is what moves with limit. The profile counters describe the member,
        # so reading totalTrades off a small page must still give the whole history.
        mock_get.return_value = _mock_response(
            json_data={
                "isPreview": False,
                "previewReason": None,
                "totalCount": 12159,
                "data": {
                    "profile": {"urlSlug": "Ro-Khanna", "totalTrades": 12159},
                    "recentTrades": [{"ticker": "NVDA", "transactionType": "purchase"}],
                    "topTickers": ["NVDA"],
                },
            }
        )
        result = client.get_politician_member("Ro-Khanna", limit=1)
        assert result.total_count == 12159
        assert len(result.recentTrades) == 1
        assert result.profile.totalTrades == 12159


class TestStockChartReturnShape:
    """The endpoint answers with a bare list of bars, not an object.

    The wheel ships ``py.typed``, so the declared return type is what type checkers
    hand callers. Declaring a mapping steered them straight into ``chart["close"]``,
    which raises at runtime on every timeframe.
    """

    def test_returns_the_bar_list_untouched(self, client):
        bars = [
            {"timestamp": 1754524800000, "open": 1.0, "high": 2.0, "low": 0.5,
             "close": 1.5, "volume": 10, "date": "Aug 07", "session": None},
            {"timestamp": 1754611200000, "open": 1.5, "high": 2.5, "low": 1.0,
             "close": 2.0, "volume": 20, "date": "Aug 08", "session": None},
        ]
        with patch.object(SentiSenseClient, "_get") as mock_get:
            mock_get.return_value = _mock_response(json_data=bars)
            result = client.get_stock_chart("AAPL", timeframe="1Y")

        assert isinstance(result, list)
        assert result[-1]["close"] == 2.0

    def test_declared_return_type_is_a_list_of_bars(self):
        from typing import Any, Dict, List

        annotation = SentiSenseClient.get_stock_chart.__annotations__["return"]
        assert annotation == List[Dict[str, Any]]

    def test_docstring_does_not_promise_a_mapping_lookup(self):
        doc = SentiSenseClient.get_stock_chart.__doc__ or ""
        assert "bare list of bars" in doc


class TestStockPriceListingStatus:
    """The price payload carries the listing lifecycle when a stock stops trading.

    The model filters unknown keys, so a field that is not declared is dropped
    silently: a delisted price would read as an ordinary live one.
    """

    @patch.object(SentiSenseClient, "_get")
    def test_listing_status_is_parsed(self, mock_get, client):
        mock_get.return_value = _mock_response(
            json_data={
                "ticker": "TWTR",
                "currentPrice": 54.2,
                "change": 0.0,
                "changePercent": 0.0,
                "previousClose": 54.2,
                "volume": 0,
                "timestamp": 1667174400,
                "listingStatus": "DELISTED",
                "delistedDate": "2022-10-27",
                "delistingReason": "take_private",
            }
        )
        result = client.get_stock_price("TWTR")
        assert result.listingStatus == "DELISTED"
        assert result.delistedDate == "2022-10-27"
        assert result.delistingReason == "take_private"
        assert result["listingStatus"] == "DELISTED"

    @patch.object(SentiSenseClient, "_get")
    def test_absent_listing_status_is_none(self, mock_get, client):
        # An ordinarily listed stock omits all three keys, which is the overwhelming
        # majority of responses. Absent must parse, not raise.
        mock_get.return_value = _mock_response(
            json_data={"ticker": "AAPL", "currentPrice": 313.33, "timestamp": 1754611200}
        )
        result = client.get_stock_price("AAPL")
        assert result.listingStatus is None
        assert result.delistedDate is None
        assert result.delistingReason is None

    @patch.object(SentiSenseClient, "_get")
    def test_batch_prices_carry_listing_status(self, mock_get, client):
        mock_get.return_value = _mock_response(
            json_data=[
                {"ticker": "AAPL", "currentPrice": 313.33},
                {
                    "ticker": "TWTR",
                    "currentPrice": 54.2,
                    "listingStatus": "DELISTED",
                    "delistedDate": "2022-10-27",
                },
            ]
        )
        results = client.get_stock_prices(["AAPL", "TWTR"])
        assert results[0].listingStatus is None
        assert results[1].listingStatus == "DELISTED"
        assert results[1].delistedDate == "2022-10-27"


class TestStockQuoteReportedCurrency:
    """The quote carries the filer's reporting currency next to its filing-derived fields.

    Dropping it silently invited the assumption that ``epsTTM`` is dollars for every
    ticker, which is wrong for a filer that reports in its home currency.
    """

    @patch.object(SentiSenseClient, "_get")
    def test_reported_currency_is_parsed(self, mock_get, client):
        mock_get.return_value = _mock_response(
            json_data={
                "ticker": "AAPL",
                "currentPrice": 313.33,
                "epsTTM": 8.1,
                "peRatio": 38.7,
                "reportedCurrency": "USD",
                "timestamp": 1754611200,
            }
        )
        result = client.get_stock_quote("AAPL")
        mock_get.assert_called_once_with("/api/v1/stocks/AAPL/quote")
        assert result.reportedCurrency == "USD"
        assert result["reportedCurrency"] == "USD"

    @patch.object(SentiSenseClient, "_get")
    def test_absent_currency_is_none_not_usd(self, mock_get, client):
        # Quotes with no filing-derived block omit the key entirely. Absent means
        # unknown, so it must not default to a currency.
        mock_get.return_value = _mock_response(
            json_data={"ticker": "TSM", "currentPrice": 300.0, "timestamp": 1754611200}
        )
        result = client.get_stock_quote("TSM")
        assert result.reportedCurrency is None
        assert result.epsTTM is None


class TestAnalystCoverage:
    """Who covers a ticker, grouped by firm.

    The response-level counts survive the FREE truncation, so a caller reading
    ``firmCount`` off a 5-row preview is reading the whole window. The row shapes
    that follow are the two the docs warn about: a firm with a rating and no note,
    and a note that names nobody.
    """

    @patch.object(SentiSenseClient, "_get")
    def test_omitting_lookback_leaves_the_window_to_the_server(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"data": {}})
        client.get_analyst_coverage("amd")
        mock_get.assert_called_once_with("/api/v1/analyst/AMD/coverage", params={})

    @patch.object(SentiSenseClient, "_get")
    def test_lookback_days_is_sent(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"data": {}})
        client.get_analyst_coverage("AMD", lookback_days=180)
        mock_get.assert_called_once_with(
            "/api/v1/analyst/AMD/coverage", params={"lookbackDays": 180}
        )

    @patch.object(SentiSenseClient, "_get")
    def test_counts_describe_the_window_not_the_returned_rows(self, mock_get, client):
        mock_get.return_value = _mock_response(
            json_data={
                "isPreview": True,
                "previewReason": "PRO_REQUIRED",
                "data": {
                    "ticker": "AMD",
                    "windowDays": 365,
                    "asOf": "2026-09-01",
                    "firmCount": 41,
                    "ratingOnlyFirmCount": 6,
                    "namedAnalystCount": 27,
                    "noteCount": 97,
                    "attributedNoteCount": 53,
                    "unattributedNoteCount": 44,
                    "attributionNote": "Publishers name the individual analyst on some notes and not others.",
                    "coverage": [
                        {
                            "firm": "Deutsche Bank",
                            "analysts": [],
                            "noteCount": 1,
                            "attributedNoteCount": 0,
                            "unattributedNoteCount": 1,
                            "firstNote": "2025-11-20",
                            "lastNote": "2025-11-20",
                            "latestNote": {
                                "publishedDate": "2025-11-20",
                                "analyst": None,
                                "priceTarget": 215.0,
                            },
                            "firmRating": {
                                "rating": "Buy",
                                "priorRating": "Buy",
                                "actionType": "REITERATE",
                                "date": "2026-08-31",
                            },
                        }
                    ],
                },
            }
        )
        result = client.get_analyst_coverage("AMD")
        assert result.is_preview is True
        assert result.preview_reason == "PRO_REQUIRED"
        # One row returned, but the counts still size the whole window.
        assert len(result.data["coverage"]) == 1
        assert result.firmCount == 41
        assert result.ratingOnlyFirmCount == 6
        # A note that names nobody is still counted and still returned.
        assert result.data["coverage"][0]["analysts"] == []
        assert result.data["coverage"][0]["latestNote"]["analyst"] is None

    @patch.object(SentiSenseClient, "_get")
    def test_rating_only_firm_has_no_note(self, mock_get, client):
        # A desk whose price target feed went quiet still covers the stock: the row
        # carries a firmRating with noteCount 0 and a null latestNote.
        mock_get.return_value = _mock_response(
            json_data={
                "isPreview": False,
                "previewReason": None,
                "data": {
                    "ticker": "AMD",
                    "firmCount": 1,
                    "ratingOnlyFirmCount": 1,
                    "coverage": [
                        {
                            "firm": "Citigroup",
                            "analysts": [],
                            "noteCount": 0,
                            "firstNote": None,
                            "lastNote": None,
                            "latestNote": None,
                            "firmRating": {
                                "rating": "Buy",
                                "priorRating": "Buy",
                                "actionType": "REITERATE",
                                "date": "2026-08-27",
                            },
                        }
                    ],
                },
            }
        )
        row = client.get_analyst_coverage("AMD").data["coverage"][0]
        assert row["noteCount"] == 0
        assert row["latestNote"] is None
        assert row["firmRating"]["rating"] == "Buy"

    @patch.object(SentiSenseClient, "_get")
    def test_named_analyst_carries_the_profile_slug(self, mock_get, client):
        mock_get.return_value = _mock_response(
            json_data={
                "isPreview": False,
                "previewReason": None,
                "data": {
                    "ticker": "NVDA",
                    "coverage": [
                        {
                            "firm": "DA Davidson",
                            "analysts": [
                                {
                                    "slug": "gil-luria",
                                    "name": "Gil Luria",
                                    "noteCount": 3,
                                    "firstNote": "2025-09-22",
                                    "lastNote": "2026-08-27",
                                    "latestPriceTarget": 300.0,
                                }
                            ],
                            "noteCount": 3,
                        }
                    ],
                },
            }
        )
        analyst = client.get_analyst_coverage("NVDA").data["coverage"][0]["analysts"][0]
        assert analyst["slug"] == "gil-luria"

    def test_unknown_ticker_raises_not_found_error(self, client):
        with patch.object(
            client.session, "get", return_value=_mock_response(404, {}, "Not Found")
        ):
            with pytest.raises(NotFoundError):
                client.get_analyst_coverage("NOSUCHTICKER")


class TestAnalystProfile:
    @patch.object(SentiSenseClient, "_get")
    def test_hits_the_people_path(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"data": {}})
        client.get_analyst_profile("dan-ives")
        mock_get.assert_called_once_with("/api/v1/analyst/people/dan-ives")

    @patch.object(SentiSenseClient, "_get")
    def test_free_book_is_truncated_and_total_count_sizes_it(self, mock_get, client):
        mock_get.return_value = _mock_response(
            json_data={
                "isPreview": True,
                "previewReason": "PRO_REQUIRED",
                "totalCount": 24,
                "data": {
                    "slug": "gil-luria",
                    "name": "Gil Luria",
                    "role": "sell_side_equity",
                    "mostRecentFirm": "DA Davidson",
                    "firms": [
                        {
                            "firm": "DA Davidson",
                            "firstSeen": "2023-01-05",
                            "lastSeen": "2026-08-27",
                            "mostRecent": True,
                        }
                    ],
                    "firstSeen": "2023-01-05",
                    "lastSeen": "2026-08-27",
                    "noteCount": 60,
                    "tickerCount": 24,
                    "coverage": [
                        {
                            "ticker": "NVDA",
                            "noteCount": 5,
                            "firstNote": "2024-05-23",
                            "lastNote": "2026-08-27",
                            "latestPriceTarget": 300.0,
                            "latestFirm": "DA Davidson",
                        }
                    ],
                },
            }
        )
        result = client.get_analyst_profile("gil-luria")
        assert result.is_preview is True
        assert result.total_count == 24
        assert result.slug == "gil-luria"
        assert result.mostRecentFirm == "DA Davidson"
        assert len(result.data["coverage"]) == 1

    def test_unknown_slug_raises_not_found_error(self, client):
        with patch.object(
            client.session, "get", return_value=_mock_response(404, {}, "Not Found")
        ):
            with pytest.raises(NotFoundError):
                client.get_analyst_profile("no-such-analyst")


class TestAnalystCalls:
    @patch.object(SentiSenseClient, "_get")
    def test_omitting_paging_leaves_it_to_the_server(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"data": []})
        client.get_analyst_calls("dan-ives")
        mock_get.assert_called_once_with(
            "/api/v1/analyst/people/dan-ives/calls", params={}
        )

    @patch.object(SentiSenseClient, "_get")
    def test_limit_and_offset_are_sent(self, mock_get, client):
        mock_get.return_value = _mock_response(json_data={"data": []})
        client.get_analyst_calls("dan-ives", limit=50, offset=25)
        mock_get.assert_called_once_with(
            "/api/v1/analyst/people/dan-ives/calls",
            params={"limit": 50, "offset": 25},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_offset_zero_is_sent(self, mock_get, client):
        # offset=0 is a real value, not "unset": it must survive the None check.
        mock_get.return_value = _mock_response(json_data={"data": []})
        client.get_analyst_calls("dan-ives", limit=5, offset=0)
        mock_get.assert_called_once_with(
            "/api/v1/analyst/people/dan-ives/calls",
            params={"limit": 5, "offset": 0},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_total_count_sizes_the_history(self, mock_get, client):
        mock_get.return_value = _mock_response(
            json_data={
                "isPreview": False,
                "previewReason": None,
                "totalCount": 60,
                "data": [
                    {
                        "publishedDate": "2026-08-27",
                        "ticker": "NVDA",
                        "firm": "DA Davidson",
                        "priceTarget": 300.0,
                        "adjPriceTarget": 300.0,
                        "priceWhenPosted": 225.64,
                        "newsTitle": "DA Davidson Reiterates Buy Rating on NVIDIA",
                        "newsUrl": "https://example.com/note",
                        "newsPublisher": "StreetInsider",
                    }
                ],
            }
        )
        result = client.get_analyst_calls("gil-luria", limit=1)
        assert result.total_count == 60
        assert len(result) == 1
        assert result[0]["ticker"] == "NVDA"
        # One row of sixty: another page is available.
        assert 0 + len(result.data) < result.total_count

    @patch.object(SentiSenseClient, "_get")
    def test_deep_offset_previews_on_a_free_key(self, mock_get, client):
        mock_get.return_value = _mock_response(
            json_data={
                "isPreview": True,
                "previewReason": "PRO_REQUIRED",
                "totalCount": 60,
                "data": [],
            }
        )
        result = client.get_analyst_calls("gil-luria", limit=25, offset=50)
        assert result.is_preview is True
        assert result.preview_reason == "PRO_REQUIRED"
        assert result.data == []

    def test_unknown_slug_raises_not_found_error(self, client):
        with patch.object(
            client.session, "get", return_value=_mock_response(404, {}, "Not Found")
        ):
            with pytest.raises(NotFoundError):
                client.get_analyst_calls("no-such-analyst")
