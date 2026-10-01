"""Tests for the typed stock graph models and ``get_stock_graph``."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sentisense import (
    GraphCounts,
    GraphEdge,
    GraphGroups,
    GraphNode,
    GraphProductFamily,
    SentiSenseClient,
    StockGraph,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "stock_graph_live.json"


@pytest.fixture(scope="module")
def payload() -> dict:
    # A trimmed copy of a real /api/v1/stocks/AAPL/graph response.
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class TestStockGraphParsing:
    def test_top_level_fields(self, payload):
        g = StockGraph.from_dict(payload)
        assert g.ticker == "AAPL"
        assert g.root == "Apple-Inc"
        assert g.depth == 1
        assert g.cap == 75
        assert g.truncated is False
        assert g.omitted == 0

    def test_nodes_are_typed(self, payload):
        g = StockGraph.from_dict(payload)
        assert g.nodes and all(isinstance(n, GraphNode) for n in g.nodes)
        root = next(n for n in g.nodes if n.slug == g.root)
        assert root.displayName == "Apple Inc."
        assert root.type == "COMPANY"

    def test_edges_are_typed_with_string_properties(self, payload):
        g = StockGraph.from_dict(payload)
        assert g.edges and all(isinstance(e, GraphEdge) for e in g.edges)
        leads = next(e for e in g.edges if e.type == "LEADS")
        assert leads.source == "Tim-Cook" and leads.target == "Apple-Inc"
        assert leads.direction == "DIRECTED"
        assert leads.properties.get("role") == "Executive Chairman"
        assert leads.properties.get("since") == "2026"
        founded = next(e for e in g.edges if e.type == "FOUNDED")
        assert founded.properties["year"] == "1976"
        peer = next(e for e in g.edges if e.type == "PEER")
        assert peer.direction == "BIDIRECTIONAL"
        assert peer.properties == {}
        for e in g.edges:
            assert all(isinstance(v, str) for v in e.properties.values())

    def test_groups_and_product_families(self, payload):
        g = StockGraph.from_dict(payload)
        assert isinstance(g.groups, GraphGroups)
        assert "Tim-Cook" in g.groups.people
        assert "Alphabet-Inc" in g.groups.peers
        fam = g.groups.productFamilies[0]
        assert isinstance(fam, GraphProductFamily)
        assert fam.family == "iPhone"
        assert "iPhone-17-Pro" in fam.members
        assert g.groups.topics == []

    def test_counts_match_the_lists(self, payload):
        g = StockGraph.from_dict(payload)
        assert isinstance(g.counts, GraphCounts)
        assert g.counts.nodes == len(g.nodes)
        assert g.counts.edges == len(g.edges)
        assert sum(g.counts.byType.values()) == len(g.nodes)

    def test_every_reference_resolves_to_a_node_slug(self, payload):
        g = StockGraph.from_dict(payload)
        slugs = {n.slug for n in g.nodes}
        for e in g.edges:
            assert e.source in slugs and e.target in slugs
        grouped = (
            g.groups.people + g.groups.products + g.groups.peers
            + [f.family for f in g.groups.productFamilies]
            + [m for f in g.groups.productFamilies for m in f.members]
        )
        assert set(grouped) <= slugs

    def test_payload_carries_no_internal_entity_ids(self, payload):
        # The graph is slug-keyed end to end; internal "kb/..." ids never appear.
        assert "kb/" not in json.dumps(payload)
        g = StockGraph.from_dict(payload)
        ids = [n.slug for n in g.nodes] + [x for e in g.edges for x in (e.source, e.target)]
        assert not [i for i in ids if i.startswith("kb/")]

    def test_missing_collections_default_empty(self):
        g = StockGraph.from_dict({"ticker": "XYZ", "root": "XYZ-Inc"})
        assert g.nodes == [] and g.edges == []
        assert g.counts is None and g.groups is None
        e = GraphEdge.from_dict({"source": "a", "target": "b", "properties": None})
        assert e.properties == {}

    def test_none_payload(self):
        assert StockGraph.from_dict(None) is None


class TestGetStockGraph:
    @patch.object(SentiSenseClient, "_get")
    def test_default_params_and_upper_cased_path(self, mock_get, payload):
        resp = MagicMock()
        resp.json.return_value = payload
        mock_get.return_value = resp
        g = SentiSenseClient("test-api-key").get_stock_graph("aapl")
        mock_get.assert_called_once_with(
            "/api/v1/stocks/AAPL/graph", params={"depth": 1, "cap": 75}
        )
        assert isinstance(g, StockGraph)
        assert g.root == "Apple-Inc"

    @patch.object(SentiSenseClient, "_get")
    def test_depth_and_cap_are_forwarded(self, mock_get, payload):
        resp = MagicMock()
        resp.json.return_value = payload
        mock_get.return_value = resp
        SentiSenseClient("test-api-key").get_stock_graph("AAPL", depth=2, cap=20)
        mock_get.assert_called_once_with(
            "/api/v1/stocks/AAPL/graph", params={"depth": 2, "cap": 20}
        )
