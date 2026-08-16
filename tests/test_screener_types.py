"""Unit tests for the screener methods.

Three contracts are gated here because getting any of them wrong produces a
screen that runs cleanly and answers the wrong question:

* ``limit`` rides next to ``plan`` on the request body, never inside it. A plan
  is a stored object; paging is a transport concern. A ``limit`` nested in the
  plan is silently ignored and the caller gets the 100-row default.
* ``matched`` is the pre-limit count, so truncation stays visible. A capped list
  with no count is how a caller concludes the universe is smaller than it is.
* Omitting ``tickers`` means the whole tracked universe, so the key must be
  absent from the body rather than sent as ``null``.

The curated plans returned by ``list_screens()`` identify their field with
``field`` rather than ``fieldName``, which is asserted here so a future
round-trip helper cannot assume only one of the two keys exists.
"""

from unittest.mock import MagicMock, patch

import pytest

from sentisense import SentiSenseClient
from sentisense.types import (
    EtfScreenerResults,
    FeaturedScreen,
    ScreenerFieldCatalog,
    ScreenerResults,
)


@pytest.fixture
def client():
    return SentiSenseClient("test-api-key")


def _mock_response(json_data=None):
    resp = MagicMock()
    resp.status_code = 200
    resp.ok = True
    resp.json.return_value = json_data if json_data is not None else {}
    return resp


FIELDS_PAYLOAD = {
    "stock": [
        {
            "name": "SENTI_SCORE_7D",
            "label": "SentiSense 7D",
            "group": "Sentiment",
            "type": "NUMBER",
            "unit": "SCORE",
            "ops": ["GTE", "GT", "LTE", "LT"],
            "sortable": True,
            "step": 1.0,
            "placeholder": "13",
            "description": "7-day SentiSense score.",
            "options": None,
            "quickValues": ["5", "13", "23"],
            "values": None,
        },
        {
            "name": "SENTIMENT_DIRECTION",
            "label": "Score Direction",
            "group": "Sentiment",
            "type": "ENUM",
            "unit": "SCORE",
            "ops": ["EQ"],
            "sortable": True,
            "description": "Which side of the neutral band the Score sits on.",
            "options": [
                {"value": 1.0, "label": "Bullish"},
                {"value": 0.0, "label": "Neutral"},
                {"value": -1.0, "label": "Bearish"},
            ],
        },
    ],
    "etf": [
        {
            "name": "ISSUER",
            "label": "Issuer",
            "group": "Fund profile",
            "type": "STRING",
            "ops": ["IN", "NOT_IN"],
            "sortable": False,
            "description": "Fund issuer.",
            "values": ["Vanguard", "iShares"],
        }
    ],
}


EXECUTE_PAYLOAD = {
    "matched": 41,
    "limit": 2,
    "results": [
        {
            "ticker": "AAPL",
            "sentiSenseScore7D": 14.2,
            "sentiSenseScore1M": 9.8,
            "scoreChange7D": 4.4,
            "sentimentDirection": 1.0,
            "analystRatingMean": 1.9,
            "maCrossState": 1.0,
            "marketCap": 3120000000000,
            "return1Y": None,
            "sentisenseScoreBars7D": [11.0, 12.5],
            "lastUpdated": 1754000000,
        },
        {"ticker": "MSFT", "sentiSenseScore7D": 11.1},
    ],
}


class TestFields:
    def test_parses_both_universes_and_enum_options(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(FIELDS_PAYLOAD)) as m:
            catalog = client.get_screener_fields()
        assert m.call_args[0][0].endswith("/api/v1/screener/fields")
        assert isinstance(catalog, ScreenerFieldCatalog)
        assert [f.name for f in catalog.stock] == ["SENTI_SCORE_7D", "SENTIMENT_DIRECTION"]
        assert catalog.stock[0].quickValues == ["5", "13", "23"]
        # ENUM fields carry their readings; NUMBER fields carry None, not [].
        assert catalog.stock[0].options is None
        assert [o.label for o in catalog.stock[1].options] == ["Bullish", "Neutral", "Bearish"]
        assert catalog.stock[1].options[2].value == -1.0

    def test_etf_string_values_survive(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(FIELDS_PAYLOAD)):
            catalog = client.get_screener_fields()
        issuer = catalog.etf[0]
        assert issuer.type == "STRING"
        assert issuer.ops == ["IN", "NOT_IN"]
        # Populated from the live universe, so a client must read it rather than
        # ship a static issuer list.
        assert issuer.values == ["Vanguard", "iShares"]


class TestScreens:
    def test_unwraps_the_envelope_into_screens(self, client):
        payload = {
            "screens": [
                {
                    "id": "crowd-vs-street",
                    "name": "Crowd vs Street",
                    "summary": "Bullish Score, few analyst buys",
                    "plan": {
                        "universe": "STOCK",
                        "filters": [{"field": "SENTI_SCORE_7D", "op": "GTE", "value": 5.0}],
                        "sort": {"field": "SENTI_SCORE_7D", "dir": "DESC"},
                    },
                }
            ]
        }
        with patch.object(client.session, "get", return_value=_mock_response(payload)) as m:
            screens = client.list_screens()
        assert m.call_args[0][0].endswith("/api/v1/screener/screens")
        assert len(screens) == 1
        assert isinstance(screens[0], FeaturedScreen)
        assert screens[0].id == "crowd-vs-street"

    def test_curated_plans_use_the_legacy_field_key(self, client):
        # These plans identify the field with `field`, not `fieldName`. Both are
        # accepted on the way in, but a consumer reading only `fieldName` off a
        # curated plan sees nothing at all.
        payload = {
            "screens": [
                {
                    "id": "winners",
                    "name": "Winners",
                    "summary": "Stocks up today",
                    "plan": {"filters": [{"field": "CHANGE_PERCENT", "op": "GT", "value": 0.0}]},
                }
            ]
        }
        with patch.object(client.session, "get", return_value=_mock_response(payload)):
            screens = client.list_screens()
        filt = screens[0].plan["filters"][0]
        assert filt["field"] == "CHANGE_PERCENT"
        assert "fieldName" not in filt

    def test_a_curated_plan_round_trips_into_run_screen(self, client):
        screens_payload = {
            "screens": [
                {
                    "id": "winners",
                    "name": "Winners",
                    "summary": "Stocks up today",
                    "plan": {"filters": [{"field": "CHANGE_PERCENT", "op": "GT", "value": 0.0}]},
                }
            ]
        }
        with patch.object(client.session, "get", return_value=_mock_response(screens_payload)):
            screen = client.list_screens()[0]
        with patch.object(client.session, "post", return_value=_mock_response(EXECUTE_PAYLOAD)) as m:
            client.run_screen(screen.plan)
        assert m.call_args[1]["json"]["plan"] == screen.plan


class TestRunScreen:
    def test_limit_sits_beside_the_plan_not_inside_it(self, client):
        plan = {"filters": [{"fieldName": "SENTI_SCORE_7D", "op": "GTE", "value": 13}]}
        with patch.object(client.session, "post", return_value=_mock_response(EXECUTE_PAYLOAD)) as m:
            client.run_screen(plan, limit=25)
        body = m.call_args[1]["json"]
        assert body["limit"] == 25
        assert "limit" not in body["plan"]
        assert m.call_args[0][0].endswith("/api/v1/screener/execute")

    def test_omitting_tickers_leaves_the_key_off_the_body(self, client):
        # Absent means the whole tracked universe. Sending an explicit null or []
        # is a different request.
        with patch.object(client.session, "post", return_value=_mock_response(EXECUTE_PAYLOAD)) as m:
            client.run_screen({"filters": []})
        assert "tickers" not in m.call_args[1]["json"]

    def test_ticker_scope_is_passed_through(self, client):
        with patch.object(client.session, "post", return_value=_mock_response(EXECUTE_PAYLOAD)) as m:
            client.run_screen({"filters": []}, tickers=["AAPL", "MSFT"])
        assert m.call_args[1]["json"]["tickers"] == ["AAPL", "MSFT"]

    def test_matched_is_the_pre_limit_count(self, client):
        with patch.object(client.session, "post", return_value=_mock_response(EXECUTE_PAYLOAD)):
            res = client.run_screen({"filters": []}, limit=2)
        assert isinstance(res, ScreenerResults)
        assert res.matched == 41
        assert res.limit == 2
        assert len(res.results) == 2

    def test_rows_keep_nulls_and_ordinals_intact(self, client):
        with patch.object(client.session, "post", return_value=_mock_response(EXECUTE_PAYLOAD)):
            res = client.run_screen({"filters": []})
        row = res.results[0]
        assert row.ticker == "AAPL"
        assert row.sentiSenseScore7D == 14.2
        # A missing reading stays None. Coercing it to 0.0 would make a stock with
        # no 1Y history look flat rather than uncovered.
        assert row.return1Y is None
        assert row.maCrossState == 1.0
        assert row.sentimentDirection == 1.0
        # Inverted vendor scale: 1.9 is bullish, not bearish.
        assert row.analystRatingMean == 1.9
        assert row.sentisenseScoreBars7D == [11.0, 12.5]
        # Fields absent from a sparse row default rather than raising.
        assert res.results[1].marketCap is None


class TestRunEtfScreen:
    def test_hits_the_etf_path_and_parses_rows(self, client):
        payload = {
            "matched": 3,
            "limit": 100,
            "results": [
                {
                    "ticker": "SPY",
                    "name": "SPDR S&P 500 ETF Trust",
                    "issuer": "SPDR",
                    "constituentsWeightedSentisense": 8.4,
                    "directSentisense": 2.1,
                    "weightCoveredPct": 91.2,
                    "expenseRatio": 0.09,
                    "holdingsCount": 503,
                }
            ],
        }
        with patch.object(client.session, "post", return_value=_mock_response(payload)) as m:
            res = client.run_etf_screen(
                {"filters": [{"fieldName": "ISSUER", "op": "IN", "values": ["SPDR"]}]},
                limit=100,
            )
        assert m.call_args[0][0].endswith("/api/v1/screener/etfs/execute")
        assert isinstance(res, EtfScreenerResults)
        row = res.results[0]
        # The two Score readings are different questions and must stay distinct.
        assert row.constituentsWeightedSentisense == 8.4
        assert row.directSentisense == 2.1
        # Percent points, not a fraction: 0.09 means 0.09%.
        assert row.expenseRatio == 0.09
        assert row.weightCoveredPct == 91.2

    def test_string_filters_send_values_not_value(self, client):
        with patch.object(client.session, "post", return_value=_mock_response({"results": []})) as m:
            client.run_etf_screen(
                {"filters": [{"fieldName": "ASSET_CLASS", "op": "IN", "values": ["Equity"]}]}
            )
        filt = m.call_args[1]["json"]["plan"]["filters"][0]
        assert filt["values"] == ["Equity"]
        assert "value" not in filt
