"""Unit tests for the options methods.

Four contracts are gated here because each one fails quietly rather than loudly:

* The radar's ``rows`` and ``etfRows`` are separately-ranked boards, and so are their
  aggregates. Merged, they sort cleanly and rank nothing, because every reading behind a
  row's score is a percentile of that ticker's own history rather than of the board.
* A row whose baseline is still building omits its percentiles and ``interestScore``.
  Read as zero, the least-*measured* name on the board reads as the least interesting one.
* The dossier reports no coverage as a ``None`` payload; the history reports it as an
  empty ``series``. A caller that null-checks the history waits for a ``None`` that never
  arrives and reads an empty chart as a live one.
* The history echoes the window the server actually served, which need not be the one
  requested: an unrecognised value clamps to ``1y``, and so does any free key.
"""

import dataclasses
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sentisense import SentiSenseClient
from sentisense.types import (
    APIModel,
    OptionsCapabilities,
    OptionsHistory,
    OptionsHighlight,
    OptionsIntradayBoardCapability,
    OptionsIntradayFlow,
    OptionsOiFollowUp,
    OptionsOverview,
    OptionsSummary,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def client():
    return SentiSenseClient("test-api-key")


def _mock_response(json_data=None):
    resp = MagicMock()
    resp.status_code = 200
    resp.ok = True
    resp.json.return_value = json_data if json_data is not None else {}
    return resp


OVERVIEW_PAYLOAD = {
    "isPreview": False,
    "previewReason": None,
    "data": {
        "asOf": "2026-08-20",
        "medianIvRank": 30.78,
        "marketPcVol": 0.646,
        "extremeCount": 198,
        "coverageCount": 1018,
        "rows": [
            {
                "ticker": "ROST",
                "name": "Ross Stores, Inc.",
                "sector": "Consumer Discretionary",
                "asOf": "2026-08-20",
                "sentiment": -0.347,
                "interestScore": 89.68,
                "pcVol": 2.5879,
                "pcVolPctl1y": 89.68,
                "atmIv": 0.4246,
                "ivRank1y": 100.0,
                "skew25d": -0.0195,
                "skewPctl1y": 10.31,
                "notionalVol": 35792776.0,
                "ivMove20": 0.0494,
                "observations1y": 252,
                "unusualCount": 5,
                "maxVolOiRatio": 47.0,
                "maxUnusualPremium": 4366064.99,
            },
            # Building baseline: raw readings, no percentiles and no score.
            {"ticker": "NEWCO", "atmIv": 0.61, "pcVol": 1.2, "observations1y": 12},
        ],
        "etfRows": [
            {
                "ticker": "VIS",
                "name": "Vanguard Industrials ETF",
                "sector": "Equity",
                "interestScore": 77.39,
                "atmIv": 0.1856,
                "unusualCount": 0,
            }
        ],
        "etfMedianIvRank": 35.72,
        "etfMarketPcVol": 0.9418,
        "etfExtremeCount": 10,
        "etfCoverageCount": 71,
    },
}


class TestOptionsOverview:
    def test_calls_the_market_wide_path_with_no_ticker(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(OVERVIEW_PAYLOAD)) as g:
            result = client.get_options_overview()
        assert "/api/v1/options/overview" in g.call_args[0][0]
        assert isinstance(result.data, OptionsOverview)
        assert result.asOf == "2026-08-20"

    def test_keeps_the_two_boards_and_their_aggregates_apart(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(OVERVIEW_PAYLOAD)):
            result = client.get_options_overview()
        assert [r.ticker for r in result.rows] == ["ROST", "NEWCO"]
        assert [r.ticker for r in result.etfRows] == ["VIS"]
        # Two boards, two coverage denominators; neither counts the other's tickers.
        assert result.coverageCount == 1018
        assert result.etfCoverageCount == 71
        # On an ETF row `sector` carries the fund's asset class, not a GICS sector.
        assert result.etfRows[0].sector == "Equity"

    def test_leaves_a_building_baseline_unscored_rather_than_zero(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(OVERVIEW_PAYLOAD)):
            result = client.get_options_overview()
        building = result.rows[1]
        assert building.atmIv == 0.61
        assert building.interestScore is None
        assert building.ivRank1y is None
        assert building.skewPctl1y is None

    def test_reports_a_truncated_free_board_without_shrinking_the_coverage_counts(self, client):
        payload = {
            "isPreview": True,
            "previewReason": "PRO_REQUIRED",
            "totalCount": 1018,
            "data": {
                "asOf": "2026-08-20",
                "coverageCount": 1018,
                "rows": [{"ticker": "ROST"}],
                "etfRows": [{"ticker": "VIS"}],
                "etfCoverageCount": 71,
                "etfTotalCount": 71,
            },
        }
        with patch.object(client.session, "get", return_value=_mock_response(payload)):
            result = client.get_options_overview()
        assert result.is_preview is True
        assert result.preview_reason == "PRO_REQUIRED"
        assert result.total_count == 1018
        assert result.etfTotalCount == 71
        assert result.coverageCount == 1018

    def test_reads_a_null_payload_as_a_cold_start(self, client):
        payload = {"isPreview": False, "previewReason": None, "data": None}
        with patch.object(client.session, "get", return_value=_mock_response(payload)):
            result = client.get_options_overview()
        assert result.data is None

    def test_parses_both_session_highlight_lists(self, client):
        stock = {
            "ticker": "NVDA", "contract": "NVDA260821C00217500", "type": "call",
            "strike": 217.5, "expiry": "2026-08-21", "dte": 1, "volume": 900,
            "oi": 100, "volOiRatio": 9.0, "premium": 19321974.0,
            "premiumPctl1y": 98.5, "oiPrior": 100, "oiNext": 650,
            "oiChange": 550, "oiConfirmation": "opened", "oiObservedAt": 1787335200,
            "oiVintage": "next_session", "asOf": "2026-08-20",
            "publishedAt": "2026-08-21T01:00:00Z", "session": "completed",
        }
        etf = {**stock, "ticker": "SPY", "contract": "SPY260821P00600000"}
        payload = {"highlights": [stock], "etfHighlights": [etf]}
        result = OptionsOverview.from_dict(payload)
        for highlight, expected in zip((result.highlights[0], result.etfHighlights[0]),
                                       (stock, etf)):
            assert isinstance(highlight, OptionsHighlight)
            for key, value in expected.items():
                assert getattr(highlight, key) == value

    def test_omitted_highlight_fields_and_lists_default_to_none_and_empty(self):
        result = OptionsOverview.from_dict({"highlights": [{}]})
        assert result.etfHighlights == []
        assert all(getattr(result.highlights[0], field) is None for field in (
            "ticker", "contract", "type", "strike", "expiry", "dte", "volume", "oi",
            "volOiRatio", "premium", "premiumPctl1y", "oiPrior", "oiNext",
            "oiChange", "oiConfirmation", "oiObservedAt", "oiVintage", "asOf",
            "publishedAt", "session",
        ))
        assert OptionsOverview.from_dict({}).highlights == []


class TestOptionsSummary:
    def test_parses_the_dossier_and_upper_cases_the_symbol(self, client):
        payload = {
            "isPreview": False,
            "previewReason": None,
            "data": {
                "asOf": "2026-08-20",
                "sentiment": -0.1198,
                "latest": {"date": "2026-08-20", "atmIv": 0.4051, "pcVol": 0.5824},
                "context": {"ivRank1y": 38.29, "observations1y": 252},
                "oiWalls": {
                    "expiry": "2026-08-21",
                    "maxPain": 210,
                    "callWalls": [{"strike": 220, "oi": 42100}],
                    "putWalls": [{"strike": 200, "oi": 31000}],
                },
                "unusual": [
                    {
                        "contract": "NVDA260821C00217500",
                        "type": "call",
                        "strike": 217.5,
                        "dte": 1,
                        "premium": 19321974.0,
                    }
                ],
            },
        }
        with patch.object(client.session, "get", return_value=_mock_response(payload)) as g:
            result = client.get_stock_options_summary("nvda")
        assert "/api/v1/stocks/NVDA/options/summary" in g.call_args[0][0]
        assert isinstance(result.data, OptionsSummary)
        assert result.latest.atmIv == 0.4051
        assert result.context.ivRank1y == 38.29
        assert result.oiWalls.callWalls[0].strike == 220
        assert result.unusual[0].type == "call"

    def test_reads_a_null_payload_as_no_coverage(self, client):
        payload = {"isPreview": False, "previewReason": None, "data": None}
        with patch.object(client.session, "get", return_value=_mock_response(payload)):
            result = client.get_stock_options_summary("ZZZZ")
        assert result.data is None
        # The plain truthiness check a caller writes first must not raise.
        assert not result
        assert len(result) == 0

    def test_a_covered_dossier_is_truthy(self, client):
        payload = {"isPreview": False, "previewReason": None, "data": {"asOf": "2026-08-20"}}
        with patch.object(client.session, "get", return_value=_mock_response(payload)):
            result = client.get_stock_options_summary("NVDA")
        assert result

    def test_leaves_omitted_readings_as_none_rather_than_zero(self, client):
        payload = {
            "isPreview": True,
            "previewReason": "PRO_REQUIRED",
            "data": {"asOf": "2026-08-20", "latest": {"date": "2026-08-20"}, "context": {}},
        }
        with patch.object(client.session, "get", return_value=_mock_response(payload)):
            result = client.get_stock_options_summary("NVDA")
        assert result.latest.pcVol is None
        assert result.context.ivRank1y is None
        assert result.unusual == []
        assert result.latest.maxUnusualPremium is None
        assert result.context.unusualPremiumPctl1y is None

    def test_parses_open_interest_follow_up_and_premium_context(self, client):
        follow_up = {
            "oiPrior": 100, "oiNext": 650, "oiChange": 550,
            "oiConfirmation": "opened", "oiObservedAt": 1787335200,
            "oiVintage": "next_session",
        }
        payload = {"isPreview": False, "previewReason": None, "data": {
            "latest": {"maxUnusualPremium": 19321974.0},
            "context": {"unusualPremiumPctl1y": 98.5},
            "unusual": [{"contract": "NVDA260821C00217500", **follow_up}],
        }}
        with patch.object(client.session, "get", return_value=_mock_response(payload)):
            result = client.get_stock_options_summary("NVDA")
        assert result.latest.maxUnusualPremium == 19321974.0
        assert result.context.unusualPremiumPctl1y == 98.5
        for key, value in follow_up.items():
            assert getattr(result.unusual[0], key) == value

    def test_omitted_open_interest_follow_up_defaults_to_none(self):
        result = OptionsSummary.from_dict({"unusual": [{}]})
        for field in ("oiPrior", "oiNext", "oiChange", "oiConfirmation",
                      "oiObservedAt", "oiVintage"):
            assert getattr(result.unusual[0], field) is None


class TestOptionsHistory:
    def test_sends_the_requested_window_and_parses_the_series(self, client):
        payload = {
            "isPreview": False,
            "previewReason": None,
            "data": {
                "ticker": "NVDA",
                "window": "2y",
                "series": [
                    {"date": "2024-08-12", "atmIv": 0.51},
                    {"date": "2026-08-20", "atmIv": 0.4051},
                ],
            },
        }
        with patch.object(client.session, "get", return_value=_mock_response(payload)) as g:
            result = client.get_stock_options_history("nvda", window="2y")
        assert "/api/v1/stocks/NVDA/options/history" in g.call_args[0][0]
        assert g.call_args[1]["params"] == {"window": "2y"}
        assert isinstance(result.data, OptionsHistory)
        assert [s.date for s in result.series] == ["2024-08-12", "2026-08-20"]

    def test_defaults_to_the_one_year_window(self, client):
        payload = {
            "isPreview": False,
            "previewReason": None,
            "data": {"ticker": "NVDA", "window": "1y", "series": []},
        }
        with patch.object(client.session, "get", return_value=_mock_response(payload)) as g:
            client.get_stock_options_history("NVDA")
        assert g.call_args[1]["params"] == {"window": "1y"}

    def test_reports_no_coverage_as_an_empty_series_not_a_null_payload(self, client):
        payload = {
            "isPreview": False,
            "previewReason": None,
            "data": {"ticker": "ZZZZ", "window": "1y", "series": []},
        }
        with patch.object(client.session, "get", return_value=_mock_response(payload)):
            result = client.get_stock_options_history("ZZZZ")
        assert result.data is not None
        assert result.series == []

    def test_echoes_the_window_actually_served(self, client):
        # An unrecognised window clamps to 1y instead of raising, and a free key is held
        # at 1y whatever it asks for, so the echoed value is the only honest axis label.
        payload = {
            "isPreview": False,
            "previewReason": None,
            "data": {"ticker": "NVDA", "window": "1y", "series": [{"date": "2025-08-14"}]},
        }
        with patch.object(client.session, "get", return_value=_mock_response(payload)):
            result = client.get_stock_options_history("NVDA", window="5y")
        assert result.window == "1y"

    def test_parses_max_unusual_premium_in_history_and_defaults_when_omitted(self):
        result = OptionsHistory.from_dict({"series": [
            {"date": "2026-08-20", "maxUnusualPremium": 19321974.0},
            {"date": "2026-08-19"},
        ]})
        assert result.series[0].maxUnusualPremium == 19321974.0
        assert result.series[1].maxUnusualPremium is None


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _assert_every_wire_key_survives(wire, model, path="data"):
    """Walk a captured response and the model parsed from it side by side.

    Every key the server sent must be a declared field holding the same value, nested
    objects must arrive as typed models, and lists of objects must keep their length.
    A field the parser drops fails here by name instead of reading as ``None`` downstream.
    """
    declared = {f.name for f in dataclasses.fields(model)}
    for key, value in wire.items():
        where = "%s.%s" % (path, key)
        assert key in declared, "%s is on the wire but %s does not declare it" % (
            where, type(model).__name__)
        parsed = getattr(model, key)
        if isinstance(value, dict):
            assert isinstance(parsed, APIModel), "%s parsed as %r" % (where, type(parsed))
            _assert_every_wire_key_survives(value, parsed, where)
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            assert len(parsed) == len(value), where
            for i, (w, m) in enumerate(zip(value, parsed)):
                assert isinstance(m, APIModel), "%s[%d] parsed as %r" % (where, i, type(m))
                _assert_every_wire_key_survives(w, m, "%s[%d]" % (where, i))
        else:
            assert parsed == value, "%s: parsed %r, wire %r" % (where, parsed, value)


class TestIntradaySessionFields:
    """The intraday session fields ride the dossier and the radar on every tier.

    The fixtures are real responses captured during a trading session and trimmed to a
    few rows. Before these fields were declared, both parsers dropped them silently, so
    a caller saw ``None`` where the server had sent a value.
    """

    def test_summary_keeps_every_field_the_server_sends(self, client):
        payload = _load("options_summary_live.json")
        with patch.object(client.session, "get", return_value=_mock_response(payload)):
            result = client.get_stock_options_summary("NVDA")
        _assert_every_wire_key_survives(payload["data"], result.data)

    def test_summary_types_the_intraday_flow_and_capabilities(self, client):
        payload = _load("options_summary_live.json")
        with patch.object(client.session, "get", return_value=_mock_response(payload)):
            result = client.get_stock_options_summary("NVDA")
        flow = result.intradayFlow
        assert isinstance(flow, OptionsIntradayFlow)
        assert flow.unusualCount == 5
        assert flow.firstSeenEt == "10:14 ET"
        assert isinstance(flow.firstSeenAt, int)
        # The board's asOf is epoch seconds; the dossier's own asOf stays an ISO date.
        assert isinstance(flow.asOf, int)
        assert isinstance(result.asOf, str)
        assert flow.live is True
        assert flow.delayMinutes == 15
        # No highlight percentile yet, so it stays None rather than reading as zero.
        assert flow.flowPctl1y is None
        assert result.largePrintCount == 25
        assert result.largestPrintPctl is None
        board = result.capabilities.intradayBoard
        assert isinstance(result.capabilities, OptionsCapabilities)
        assert isinstance(board, OptionsIntradayBoardCapability)
        assert board.apiData is False
        assert board.access == "signed_in_pro"
        assert board.url == "https://app.sentisense.ai/options"

    def test_overview_keeps_every_field_the_server_sends(self, client):
        payload = _load("options_overview_live.json")
        with patch.object(client.session, "get", return_value=_mock_response(payload)):
            result = client.get_options_overview()
        _assert_every_wire_key_survives(payload["data"], result.data)
        assert result.intradayActiveCount == 107
        assert len(result.intradayRanking) == 25
        assert all(isinstance(t, str) for t in result.intradayRanking)
        assert result.highlightPolicy == "ex0dte-v1"
        assert result.etfHighlightPolicy == "ex0dte-v1"
        assert isinstance(result.builtAt, int)
        assert result.capabilities.intradayBoard.apiData is False

    def test_history_rows_keep_the_ex0dte_premium_and_open_interest_follow_up(self, client):
        payload = _load("options_history_live.json")
        with patch.object(client.session, "get", return_value=_mock_response(payload)):
            result = client.get_stock_options_history("NVDA")
        _assert_every_wire_key_survives(payload["data"], result.data)
        older, newer = result.series
        assert older.unusualOi is None
        assert older.maxUnusualPremiumEx0dte is None
        assert newer.maxUnusualPremiumEx0dte > 0
        assert newer.unusualOi and all(isinstance(u, OptionsOiFollowUp) for u in newer.unusualOi)

    def test_absent_intraday_fields_stay_none(self):
        summary = OptionsSummary.from_dict({"asOf": "2026-09-29"})
        for name in ("intradayFlow", "largePrintCount", "largestPrintPctl", "capabilities"):
            assert getattr(summary, name) is None
        overview = OptionsOverview.from_dict({"asOf": "2026-09-29"})
        for name in ("builtAt", "highlightPolicy", "etfHighlightPolicy",
                     "intradayActiveCount", "intradayRanking", "capabilities"):
            assert getattr(overview, name) is None

    def test_an_empty_ranking_is_kept_apart_from_an_absent_one(self):
        # A board with no active stocks sends an empty list and a zero count; before the
        # day's first board both are omitted. The two must not collapse into one value.
        quiet = OptionsOverview.from_dict({"intradayActiveCount": 0, "intradayRanking": []})
        assert quiet.intradayActiveCount == 0
        assert quiet.intradayRanking == []

    def test_unknown_keys_inside_the_new_objects_are_ignored(self):
        summary = OptionsSummary.from_dict({
            "intradayFlow": {"unusualCount": 1, "someFutureField": 1},
            "capabilities": {"intradayBoard": {"access": "power_user", "other": True},
                             "someFutureCapability": {}},
        })
        assert summary.intradayFlow.unusualCount == 1
        assert summary.capabilities.intradayBoard.access == "power_user"


def test_no_response_model_declares_a_field_named_data():
    """``PreviewResult.data`` unwraps the payload, so a model field of the same name is
    shadowed by the proxy and silently returns the whole model instead of the field.

    Gated rather than written down: the failure is invisible at the call site, and the
    rule applies to every model added from here on, not only to the options family.
    """
    import dataclasses

    from sentisense import types as t

    offenders = [
        cls.__name__
        for cls in vars(t).values()
        if isinstance(cls, type)
        and dataclasses.is_dataclass(cls)
        and issubclass(cls, t.APIModel)
        and any(f.name == "data" for f in dataclasses.fields(cls))
    ]
    assert offenders == [], (
        "these models declare a field named 'data', which PreviewResult.data shadows: "
        + ", ".join(offenders)
    )
