"""Optional response fields and compatibility with earlier payloads."""

import json
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from sentisense import (
    AnalystAction,
    AnalystEarningsSurprise,
    EarningsEvent,
    GraphNode,
    Insight,
    InstitutionDetail,
    OptionsSummary,
    RankedReportedEarnings,
    SentiSenseClient,
    StockQuote,
    StockRating,
)

PAYLOADS = json.loads(
    (Path(__file__).parent / "fixtures" / "response_additions.json").read_text()
)


def call_with_payload(method, payload, *args, **kwargs):
    client = SentiSenseClient("test-api-key")
    response = MagicMock(status_code=200, ok=True)
    response.json.return_value = payload
    with patch.object(client.session, "get", return_value=response):
        return getattr(client, method)(*args, **kwargs)


@pytest.mark.parametrize(
    "fixture,status,date",
    [
        ("optionsDelisted", "DELISTED", "2026-08-05"),
        ("optionsDelistedUnknownDate", "DELISTED", None),
        ("optionsListed", None, None),
    ],
)
def test_options_listing_fields(fixture, status, date):
    result = call_with_payload("get_stock_options_summary", PAYLOADS[fixture], "EA")
    assert isinstance(result.data, OptionsSummary)
    assert result.listingStatus == status
    assert result.delistedDate == date
    assert result["listingStatus"] == status
    assert result["delistedDate"] == date
    assert result.asOf == "2026-08-04"
    assert result.latest.atmIv == 0.0
    assert result.context.ivRank1y == 0.0


def test_surprise_percentages_are_passed_through_without_rescaling():
    result = call_with_payload("get_analyst_estimates", PAYLOADS["estimates"], "ADI")
    assert isinstance(result.data, dict)
    surprises = result.data["surprises"]
    assert all(isinstance(row, dict) for row in surprises)
    row = cast(AnalystEarningsSurprise, surprises[0])
    assert row["surprisePct"] == 3.29
    assert row["surprisePercent"] == 0.03
    assert surprises[1]["surprisePct"] == 50.0
    assert surprises[2]["surprisePct"] is None
    legacy = call_with_payload("get_analyst_estimates", PAYLOADS["estimatesLegacy"], "ADI")
    assert "surprisePct" not in legacy.data["surprises"][0]
    assert legacy.data["surprises"][0]["surprisePercent"] == 0.03


@pytest.mark.parametrize(
    "fixture,count",
    [("earningsSummaries", 9), ("earningsSummariesEmpty", 0), ("earningsSummariesLegacy", None)],
)
def test_earnings_index_count_stays_on_the_envelope(fixture, count):
    result = call_with_payload("get_earnings_summaries", PAYLOADS[fixture], "ADI", limit=1)
    assert result.is_preview is False
    assert result.total_count == count
    assert len(result.data) == len(PAYLOADS[fixture]["data"])
    assert all(not hasattr(quarter, "totalCount") for quarter in result.data)


@pytest.mark.parametrize("preview", [False, True])
def test_institution_positions_count_describes_the_full_portfolio(preview):
    payload = dict(PAYLOADS["institutionDetail"], isPreview=preview,
                   previewReason="PRO_REQUIRED" if preview else None)
    result = call_with_payload("get_institution_detail", payload, "1067983")
    detail = cast(InstitutionDetail, result.data)
    assert isinstance(detail, dict)
    assert detail["positionsHeld"] == 3
    assert result.positionsHeld == 3
    assert result["positionsHeld"] == 3
    assert detail["holdingsCount"] == 4
    assert detail["soldOutPositions"] == 1
    assert len(detail["holdings"]) == 1
    assert result.is_preview is preview
    legacy = dict(payload, data={k: v for k, v in detail.items() if k != "positionsHeld"})
    assert "positionsHeld" not in call_with_payload("get_institution_detail", legacy, "1067983").data


@pytest.mark.parametrize("category", ["Smartphones", "", "  Mixed Case Category  ", None])
def test_product_graph_category_is_unmodified_and_optional(category):
    wire = dict(PAYLOADS["stockGraph"])
    product = dict(wire["nodes"][1])
    if category is None:
        product.pop("category")
    else:
        product["category"] = category
    wire["nodes"] = [wire["nodes"][0], product, wire["nodes"][2]]
    graph = call_with_payload("get_stock_graph", wire, "AAPL")
    assert isinstance(graph.nodes[1], GraphNode)
    assert graph.nodes[1].category == category
    assert graph.nodes[1]["category"] == category
    assert graph.nodes[0].category is None
    assert graph.nodes[2].category is None


def test_dictionary_annotations_have_no_required_keys():
    assert AnalystEarningsSurprise.__total__ is False
    assert InstitutionDetail.__total__ is False
    assert "surprisePct" in AnalystEarningsSurprise.__annotations__
    assert "positionsHeld" in InstitutionDetail.__annotations__
    assert AnalystEarningsSurprise() == {}
    assert InstitutionDetail() == {}


def test_positional_construction_keeps_the_existing_arguments():
    assert GraphNode("phone", "Phone", "PRODUCT_OR_SERVICE").category is None
    assert OptionsSummary("2026-08-04", -0.12).listingStatus is None


def test_sample_flag_survives_the_preview_envelope():
    payload = {
        "isPreview": False,
        "sampleCompany": True,
        "data": {"ticker": "AAPL", "companyName": "Apple Inc.", "kpis": []},
    }
    result = call_with_payload("get_company_kpis", payload, "AAPL")
    assert result.sample_company is True
    assert result.is_preview is False
    assert result.ticker == "AAPL"


def test_sample_flag_survives_the_earnings_summaries_subclass():
    payload = {"isPreview": False, "sampleCompany": True, "ticker": "AAPL", "data": []}
    result = call_with_payload("get_earnings_summaries", payload, "AAPL")
    assert result.sample_company is True
    assert result.ticker == "AAPL"


def test_envelope_without_sample_still_parses():
    payload = {
        "isPreview": False,
        "data": {"ticker": "AAPL", "companyName": "Apple Inc.", "kpis": []},
    }
    result = call_with_payload("get_company_kpis", payload, "AAPL")
    assert result.sample_company is None
    assert result.is_preview is False


def test_sample_tickers_survive_in_the_upgrade_object():
    payload = {
        "isPreview": True,
        "previewReason": "PRO_REQUIRED",
        "upgrade": {"plan": "PRO", "message": "Upgrade", "sampleTickers": ["TSLA", "MSFT"]},
        "data": {"ticker": "MSFT", "companyName": "Microsoft", "kpis": []},
    }
    result = call_with_payload("get_company_kpis", payload, "MSFT")
    assert result.is_preview is True
    assert result.sample_company is None
    assert result.upgrade["sampleTickers"] == ["TSLA", "MSFT"]


def test_upgrade_without_sample_tickers_still_parses():
    payload = {
        "isPreview": True,
        "previewReason": "PRO_REQUIRED",
        "upgrade": {"plan": "PRO", "message": "Upgrade"},
        "data": {"ticker": "MSFT", "companyName": "Microsoft", "kpis": []},
    }
    result = call_with_payload("get_company_kpis", payload, "MSFT")
    assert result.upgrade.get("sampleTickers") is None


def test_kpi_coverage_rows_carry_the_sample_flag_when_present():
    payload = {
        "count": 2,
        "tickers": [
            {"ticker": "AAPL", "companyName": "Apple Inc.", "lastUpdated": "2026-04-30", "kpiCount": 8, "sampleCompany": True},
            {"ticker": "TSLA", "companyName": "Tesla, Inc.", "lastUpdated": "2026-04-15", "kpiCount": 6},
        ],
    }
    coverage = call_with_payload("list_kpi_coverage", payload)
    assert coverage.tickers[0].sampleCompany is True
    assert coverage.tickers[1].sampleCompany is None
    assert coverage.tickers[1].kpiCount == 6


def test_the_retired_bare_sample_key_is_not_read():
    payload = {
        "isPreview": False,
        "sample": True,
        "data": {"ticker": "AAPL", "companyName": "Apple Inc.", "kpis": []},
    }
    result = call_with_payload("get_company_kpis", payload, "AAPL")
    assert result.sample_company is None
    assert not hasattr(result, "sample")
    row = {"ticker": "AAPL", "kpiCount": 8, "sample": True}
    coverage = call_with_payload("list_kpi_coverage", {"count": 1, "tickers": [row]})
    # The retired key is never read as sampleCompany. Like any undeclared key it is
    # still visible as received, but only as an extra, never as a typed field.
    assert coverage.tickers[0].sampleCompany is None
    assert "sample" not in type(coverage.tickers[0]).__dataclass_fields__
    assert dict(coverage.tickers[0].extra_fields) == {"sample": True}


@pytest.mark.parametrize("method,args", [
    ("get_analyst_actions", ("NVDA",)),
    ("get_analyst_market_activity", ()),
])
def test_action_rows_carry_price_target_and_prior(method, args):
    result = call_with_payload(method, PAYLOADS["analystActions"], *args)
    rows = result.data
    assert isinstance(rows, list)
    assert all(isinstance(row, dict) for row in rows)
    barclays, blair, bernstein = (cast(AnalystAction, row) for row in rows)
    assert bernstein["firm"] == "Bernstein"
    assert bernstein["priceTarget"] == 200.0
    assert bernstein["priorPriceTarget"] == 400.0
    # A kept target serves no prior; a row with no stated target serves neither.
    assert barclays["priceTarget"] == 210.0
    assert barclays["priorPriceTarget"] is None
    assert blair["priceTarget"] is None
    assert blair["priorPriceTarget"] is None


def test_free_preview_action_rows_carry_null_targets():
    result = call_with_payload("get_analyst_actions", PAYLOADS["analystActionsPreview"], "NVDA")
    assert result.is_preview
    row = result.data[0]
    assert row["priceTarget"] is None
    assert row["priorPriceTarget"] is None


def test_action_rows_without_targets_still_parse():
    result = call_with_payload("get_analyst_actions", PAYLOADS["analystActionsLegacy"], "NVDA")
    row = result.data[0]
    assert row["toGrade"] == "Market Perform"
    assert row.get("priceTarget") is None
    assert row.get("priorPriceTarget") is None


def test_analyst_action_annotation_names_the_wire_keys():
    keys = AnalystAction.__annotations__
    for key in ("ticker", "actionDate", "firm", "actionType", "fromGrade", "toGrade",
                "priceTarget", "priorPriceTarget"):
        assert key in keys
    assert AnalystAction.__total__ is False


# ── Documented fields the typed models now declare ──────────────────────────


def _envelope(data):
    return {"isPreview": False, "previewReason": None, "data": data}


_LATEST_ROW = {
    "ticker": "AAPL",
    "companyName": "Apple Inc.",
    "earningsDate": "2026-11-02",
    "earningsTime": "after_close",
    "fiscalQuarter": "Q4 2026",
    "confirmed": True,
    "estimatedEps": 1.50,
    "actualEps": 1.60,
    "epsSurprisePct": 6.67,
    "epsBasis": "adjusted",
}


def test_ticker_calendar_types_the_latest_reported_row():
    payload = _envelope({"earnings": [], "metadata": {"count": 0}, "latestReported": _LATEST_ROW})
    cal = call_with_payload("get_earnings_calendar", payload, ticker="AAPL")
    latest = cal.latestReported
    assert isinstance(latest, EarningsEvent)
    assert latest.earningsDate == "2026-11-02"
    assert latest.actualEps == 1.60
    assert latest.epsBasis == "adjusted"
    # Independent of the window: present while `earnings` is empty.
    assert cal.earnings == []
    assert "latestReported" not in cal.extra_fields


def test_market_wide_calendar_has_no_latest_reported():
    cal = call_with_payload("get_earnings_calendar", _envelope({"earnings": [], "metadata": {}}))
    assert cal.latestReported is None


def test_insight_rows_name_their_ticker():
    rows = [
        {"insightType": "sentiment_shift", "insightText": "t", "ticker": "TSLA"},
        {"insightType": "market_theme", "insightText": "t", "ticker": None},
        {"insightType": "market_theme", "insightText": "t"},
    ]
    result = call_with_payload("get_latest_insights", _envelope(rows))
    assert [i.ticker for i in result] == ["TSLA", None, None]
    assert all(isinstance(i, Insight) for i in result)


def test_fund_quote_carries_see_instead():
    payload = {"ticker": "SPY", "currentPrice": 1.0, "seeInstead": ["/api/v1/etfs/SPY/quote"]}
    quote = call_with_payload("get_stock_quote", payload, "SPY")
    assert isinstance(quote, StockQuote)
    assert quote.seeInstead == ["/api/v1/etfs/SPY/quote"]
    assert call_with_payload("get_stock_quote", {"ticker": "AAPL"}, "AAPL").seeInstead is None


def test_rating_carries_company_name_and_beta_notice():
    payload = {"ticker": "AAPL", "rated": True, "companyName": "Apple Inc.", "betaNotice": "Beta: n"}
    rating = call_with_payload("get_rating", payload, "AAPL")
    assert rating.companyName == "Apple Inc."
    assert rating.betaNotice == "Beta: n"
    assert dict(rating.extra_fields) == {}
    legacy = call_with_payload("get_rating", {"ticker": "AAPL", "rated": False}, "AAPL")
    assert legacy.companyName is None and legacy.betaNotice is None


def test_ranked_reported_rows_carry_the_surprise_flag():
    payload = _envelope({
        "asOf": 1,
        "reported": {"rows": [
            {"ticker": "AAA", "outcome": "BEAT", "estimateEps": -0.10, "actualEps": 0.20,
             "surpriseFlag": "SIGN_FLIP"},
            {"ticker": "BBB", "outcome": "BEAT", "surprisePct": 4.0},
        ]},
        "upcoming": {"rows": []},
    })
    rows = call_with_payload("get_ranked_earnings", payload).reported.rows
    assert rows[0].surpriseFlag == "SIGN_FLIP" and rows[0].surprisePct is None
    assert rows[1].surpriseFlag is None and rows[1].surprisePct == 4.0


def test_new_fields_append_after_the_existing_positional_arguments():
    # Each class grew at its end, so positional construction binds as before.
    assert StockQuote("SPY", 1.0).seeInstead is None
    assert Insight("t", "x", 0.5).ticker is None
    assert StockRating("AAPL").companyName is None
    assert RankedReportedEarnings("AAA", "2026-11-02").surpriseFlag is None
