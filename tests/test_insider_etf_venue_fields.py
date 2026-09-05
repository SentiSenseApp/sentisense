"""Optional fields added in 0.51.0: insider security basis, ETF holding venue fields,
and the upgrade hint on preview results."""

from sentisense.types import EtfHolding, InsiderTrade, PreviewResult


def test_insider_trade_security_basis_parses_and_defaults_to_none():
    row = InsiderTrade.from_dict(
        {"ticker": "TSM", "securityBasis": "ORDINARY_SHARES", "pricePerShare": None}
    )
    assert row.securityBasis == "ORDINARY_SHARES"
    assert row.pricePerShare is None

    plain = InsiderTrade.from_dict({"ticker": "AAPL"})
    assert plain.securityBasis is None


def test_etf_holding_venue_fields_parse_and_default_to_none():
    foreign = EtfHolding.from_dict(
        {
            "ticker": "ROG",
            "weightPct": 1.2,
            "exchange": "SIX",
            "localTicker": "ROG",
            "linkedTicker": None,
        }
    )
    assert foreign.exchange == "SIX"
    assert foreign.localTicker == "ROG"
    assert foreign.linkedTicker is None

    domestic = EtfHolding.from_dict({"ticker": "AAPL", "weightPct": 7.0, "linkedTicker": "AAPL"})
    assert domestic.linkedTicker == "AAPL"
    assert domestic.exchange is None

    legacy = EtfHolding.from_dict({"ticker": "MSFT", "weightPct": 6.5})
    assert legacy.exchange is None and legacy.localTicker is None and legacy.linkedTicker is None


def test_preview_result_carries_optional_upgrade_hint():
    hint = {"tier": "PRO", "url": "https://app.sentisense.ai/pricing"}
    gated = PreviewResult({"rows": []}, True, "PRO_REQUIRED", 120, hint)
    assert gated.is_preview is True
    assert gated.upgrade == hint

    full = PreviewResult({"rows": []}, False, None, 120)
    assert full.upgrade is None
