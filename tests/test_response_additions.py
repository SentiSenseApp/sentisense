"""Optional response fields and compatibility with earlier payloads."""

import json
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from sentisense import (
    AnalystEarningsSurprise,
    GraphNode,
    InstitutionDetail,
    OptionsSummary,
    SentiSenseClient,
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
