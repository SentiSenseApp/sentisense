"""Round-trip tests for the typed ETF dataclasses and PreviewResult fallback."""

import pytest

from sentisense import (
    EtfAggregateCoverage,
    EtfAnalystAggregate,
    EtfAnalystContributor,
    EtfHoldings,
    EtfInfo,
    EtfInsiderAggregate,
    EtfInsiderContributor,
    EtfSentimentAggregate,
    EtfSentimentReading,
    PreviewResult,
    WeightedConsensus,
    WeightedNetFlow,
)


class TestEtfInfo:
    def test_from_dict_full(self):
        info = EtfInfo.from_dict({
            "ticker": "QQQ",
            "name": "Invesco QQQ Trust",
            "kbEntityId": "kb/etf/22",
            "urlSlug": "Invesco-QQQ-Trust",
            "issuer": "Invesco",
            "trackedIndex": "Nasdaq-100 Index",
            "assetClass": "Equity",
        })
        assert info.ticker == "QQQ"
        assert info.issuer == "Invesco"
        # dict-style + attribute-style access both work
        assert info["name"] == "Invesco QQQ Trust"

    def test_from_dict_ignores_unknown(self):
        info = EtfInfo.from_dict({"ticker": "SPY", "name": "SPDR S&P 500", "futureField": "ignored"})
        assert info.ticker == "SPY"


class TestEtfHoldings:
    def test_from_dict_with_partial(self):
        h = EtfHoldings.from_dict({
            "ticker": "QQQ",
            "issuer": "Invesco",
            "issuerEndpoint": "https://...",
            "asOfDate": "2026-05-15",
            "fetchedAt": "2026-05-15T12:00:00Z",
            "nextRefreshDue": "2026-05-16T12:00:00Z",
            "totalHoldings": 25,
            "holdings": [
                {"ticker": "AAPL", "name": "Apple Inc.", "weightPct": 9.5, "firstSeen": "2024-01-01"},
                {"ticker": "MSFT", "name": "Microsoft", "weightPct": 8.7, "firstSeen": "2024-01-01"},
            ],
            "partial": True,
            "totalKnownHoldings": 104,
        })
        assert h.ticker == "QQQ"
        assert h.partial is True
        assert h.totalKnownHoldings == 104
        assert len(h.holdings) == 2
        assert h.holdings[0].ticker == "AAPL"
        assert h.holdings[0].weightPct == 9.5

    def test_from_dict_omitted_partial(self):
        h = EtfHoldings.from_dict({
            "ticker": "SPY",
            "issuer": "SPDR",
            "issuerEndpoint": None,
            "asOfDate": "2026-05-15",
            "fetchedAt": "2026-05-15T12:00:00Z",
            "nextRefreshDue": "2026-05-16T12:00:00Z",
            "totalHoldings": 504,
            "holdings": [],
        })
        assert h.partial is None
        assert h.totalKnownHoldings is None


class TestEtfAnalystAggregate:
    def test_from_dict_free_tier_no_contributors(self):
        agg = EtfAnalystAggregate.from_dict({
            "ticker": "QQQ",
            "asOfDate": "2026-05-15",
            "computedAt": "2026-05-15T12:00:00Z",
            "coverage": {
                "holdingsCount": 25,
                "holdingsCovered": 24,
                "weightCovered": 69.25,
                "partial": True,
                "totalKnownHoldings": 104,
            },
            "weightedConsensus": {
                "upsidePercent": 7.59,
                "consensusLabel": "BUY",
                "distribution": {"BUY": 0.94, "HOLD": 0.06},
                "totalAnalysts": 938,
            },
            "topContributors": None,  # FREE: null/absent on the wire, normalized to []
        })
        assert agg.ticker == "QQQ"
        assert isinstance(agg.coverage, EtfAggregateCoverage)
        assert agg.coverage.weightCovered == 69.25
        assert isinstance(agg.weightedConsensus, WeightedConsensus)
        assert agg.weightedConsensus.consensusLabel == "BUY"
        assert agg.topContributors == []

    def test_from_dict_pro_tier_with_contributors(self):
        agg = EtfAnalystAggregate.from_dict({
            "ticker": "QQQ",
            "asOfDate": "2026-05-15",
            "computedAt": "2026-05-15T12:00:00Z",
            "coverage": {"holdingsCount": 25, "holdingsCovered": 24, "weightCovered": 69.25},
            "weightedConsensus": {"upsidePercent": 7.59, "consensusLabel": "BUY", "distribution": {}, "totalAnalysts": 938},
            "topContributors": [
                {"ticker": "AAPL", "weightPct": 9.5, "upsidePercent": 12.0, "consensusLabel": "BUY", "contributionPp": 1.14},
            ],
        })
        assert len(agg.topContributors) == 1
        assert isinstance(agg.topContributors[0], EtfAnalystContributor)
        assert agg.topContributors[0].contributionPp == 1.14


class TestEtfInsiderAggregate:
    def test_from_dict_with_lookback(self):
        agg = EtfInsiderAggregate.from_dict({
            "ticker": "ARKK",
            "asOfDate": "2026-05-15",
            "computedAt": "2026-05-15T12:00:00Z",
            "lookbackDays": 90,
            "coverage": {"holdingsCount": 24, "holdingsCovered": 17, "weightCovered": 60.69},
            "weightedNetFlow": {
                "netDollars": -65349208,
                "buyDollars": 100000,
                "sellDollars": 65449208,
                "buyTradeCount": 5,
                "sellTradeCount": 120,
                "distinctInsiderCount": 80,
            },
            "topContributors": None,
        })
        assert agg.lookbackDays == 90
        assert isinstance(agg.weightedNetFlow, WeightedNetFlow)
        assert agg.weightedNetFlow.netDollars == -65349208


class TestEtfSentimentAggregate:
    def test_from_dict_both_readings(self):
        agg = EtfSentimentAggregate.from_dict({
            "ticker": "QQQ",
            "asOfDate": "2026-05-15",
            "computedAt": "2026-05-15T12:00:00Z",
            "coverage": {"holdingsCount": 25, "holdingsCovered": 25, "weightCovered": 100.0},
            "constituentsWeighted": {
                "sentiSenseScore": 62.4,
                "scoreLabel": "BULLISH",
                "asOfTimestamp": 1778969300000,
            },
            "direct": {
                "sentiSenseScore": 58.1,
                "scoreLabel": "BULLISH",
                "asOfTimestamp": 1778969300000,
            },
        })
        assert isinstance(agg.constituentsWeighted, EtfSentimentReading)
        assert agg.constituentsWeighted.sentiSenseScore == 62.4
        assert agg.direct.scoreLabel == "BULLISH"

    def test_from_dict_direct_null(self):
        """Low-mention ETF: direct is null."""
        agg = EtfSentimentAggregate.from_dict({
            "ticker": "VOO",
            "asOfDate": "2026-05-15",
            "computedAt": "2026-05-15T12:00:00Z",
            "coverage": {"holdingsCount": 25, "holdingsCovered": 23, "weightCovered": 45.47},
            "constituentsWeighted": {"sentiSenseScore": 60.0, "scoreLabel": "BULLISH"},
            "direct": None,
        })
        assert agg.direct is None


class TestPreviewResultFallback:
    """The PreviewResult proxy must support attribute access for both dataclass-backed
    and dict-backed wrapped data. The dict-backed path is a safety net for endpoints
    that haven't migrated to typed dataclasses yet."""

    def test_attribute_access_on_dataclass(self):
        agg = EtfAnalystAggregate(ticker="QQQ", asOfDate="2026-05-15", computedAt="...")
        pr = PreviewResult(agg, is_preview=True, preview_reason="PRO_REQUIRED")
        # Attribute on the dataclass — works via getattr.
        assert pr.ticker == "QQQ"
        # Proxy metadata.
        assert pr.is_preview is True
        assert pr.preview_reason == "PRO_REQUIRED"

    def test_attribute_access_falls_back_to_dict_keys(self):
        """Wrap a raw dict and verify attribute access still works via the dict-key fallback."""
        pr = PreviewResult({"ticker": "SPY", "weightCovered": 95.3}, is_preview=False, preview_reason=None)
        # __getattr__ raises on dict initially, then falls through to the dict-key path.
        assert pr.ticker == "SPY"
        assert pr.weightCovered == 95.3

    def test_attribute_access_unknown_key_raises(self):
        pr = PreviewResult({"ticker": "SPY"}, is_preview=False, preview_reason=None)
        try:
            _ = pr.nonexistent
            assert False, "Should have raised AttributeError"
        except AttributeError:
            pass

    def test_item_access_still_works_on_dict(self):
        pr = PreviewResult({"ticker": "SPY"}, is_preview=False, preview_reason=None)
        assert pr["ticker"] == "SPY"


class TestPreviewResultTruthiness:
    """``if result:`` must not raise, whatever the payload; ``len()`` and iteration must
    not raise on a None payload or on the list and dict payloads the API returns."""

    def test_none_payload_is_falsy_with_zero_length(self):
        # An uncovered or unknown ticker comes back as a None payload.
        pr = PreviewResult(None, is_preview=False, preview_reason=None)
        assert not pr
        assert bool(pr) is False
        assert len(pr) == 0
        assert list(pr) == []
        assert pr.data is None

    def test_object_payload_is_truthy(self):
        agg = EtfAnalystAggregate(ticker="QQQ", asOfDate="2026-05-15", computedAt="...")
        pr = PreviewResult(agg, is_preview=False, preview_reason=None)
        assert pr
        assert bool(pr) is True

    def test_object_payload_still_has_no_length(self):
        # A dataclass has no length; that stays a TypeError rather than a made-up number.
        agg = EtfAnalystAggregate(ticker="QQQ", asOfDate="2026-05-15", computedAt="...")
        pr = PreviewResult(agg, is_preview=False, preview_reason=None)
        with pytest.raises(TypeError):
            len(pr)

    def test_list_payload_truthiness_and_length_unchanged(self):
        empty = PreviewResult([], is_preview=True, preview_reason="PRO_REQUIRED", total_count=0)
        full = PreviewResult([1, 2], is_preview=False, preview_reason=None, total_count=2)
        assert not empty and len(empty) == 0 and list(empty) == []
        assert full and len(full) == 2 and list(full) == [1, 2]

    def test_dict_payload_truthiness_and_length_unchanged(self):
        assert not PreviewResult({}, is_preview=False, preview_reason=None)
        pr = PreviewResult({"ticker": "SPY"}, is_preview=False, preview_reason=None)
        assert pr and len(pr) == 1 and list(pr) == ["ticker"]

    def test_scalar_and_string_payloads_follow_python_truthiness(self):
        assert not PreviewResult("", is_preview=False, preview_reason=None)
        assert PreviewResult("x", is_preview=False, preview_reason=None)
        zero = PreviewResult(0, is_preview=False, preview_reason=None)
        assert not zero
        with pytest.raises(TypeError):
            len(zero)

    def test_metadata_readable_on_none_payload(self):
        pr = PreviewResult(None, is_preview=True, preview_reason="PRO_REQUIRED", total_count=5)
        assert pr.is_preview is True
        assert pr.preview_reason == "PRO_REQUIRED"
        assert pr.total_count == 5
