"""Unit tests for the SentiSense Rating method.

Four contracts are gated here because each one fails quietly rather than loudly:

* Not being rated is a ``200`` with ``rated`` false, never a ``404``. A caller that
  treats "no grade" as an error surfaces an exception for every ETF it asks about.
* An absent dimension is a full row with ``present`` false and a ``None`` percentile.
  Read as zero, the dimension we know nothing about reads as the worst one in the
  cross-section.
* ``letter`` is the band of ``score``, not of ``percentile``, and it is served as
  stored. A client that recomputes it from the percentile disagrees with the API for
  every stock carrying a risk condition.
* ``score`` is ``percentile`` less the summed ``riskAdjustments`` points, and a
  condition is graded rather than binary, so the points are read off the response
  instead of multiplied out from how many conditions are listed.
* ``score``, ``bucketLetter``, ``riskConditions``, ``riskAdjustments`` and
  ``penaltyPoints`` are optional: a response served before they shipped omits them and
  must still parse.
* Only the smart-money dimension carries ``subLegs``. Every other dimension omits the
  field, which must parse as "no legs" rather than raising.

The payloads are trimmed copies of live responses.
"""

import re
from unittest.mock import MagicMock, patch

import pytest

from sentisense import NotFoundError, SentiSenseClient
from sentisense.types import (
    RatingDimension,
    RatingFlag,
    RatingSubLeg,
    RiskAdjustment,
    StockRating,
)


@pytest.fixture
def client():
    return SentiSenseClient("test-api-key")


def _mock_response(json_data=None, status_code=200, reason="OK"):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.reason = reason
    resp.json.return_value = json_data if json_data is not None else {}
    return resp


DISCLAIMER = (
    "The SentiSense Rating is a relative, automatically generated research signal for "
    "informational and educational purposes only. It is not financial, investment or "
    "trading advice, and it is not a recommendation about any security."
)

RATED_PAYLOAD = {
    "ticker": "AAPL",
    "kbEntityId": "kb/company/1",
    "rated": True,
    "score": 59.5,
    "letter": "C",
    "bucketLetter": "B",
    "percentile": 79.96146435452793,
    "composite": 0.21454864250697855,
    "riskConditions": ["unprofitable", "high_leverage"],
    "riskAdjustments": [
        {"condition": "unprofitable", "points": 12.0},
        {"condition": "high_leverage", "points": 8.5},
    ],
    "penaltyPoints": 20.5,
    "ratedCount": 1038,
    "asOf": "2026-09-03",
    "methodologyVersion": "2026.09-v1",
    "dimensions": [
        {
            "key": "crowd",
            "label": "Crowd sentiment",
            "percentile": 86.0488798370672,
            "raw": 9.16962530776088,
            "rawLabel": "7-day SentiSense Score",
            "present": True,
        },
        {
            "key": "smart_money",
            "label": "Smart money",
            "percentile": 44.55159112825458,
            "raw": None,
            "rawLabel": None,
            "present": True,
            "subLegs": [
                {"key": "inst_13f", "label": "13F net change", "raw": 4.01649118338024, "unit": "%"},
                {"key": "insider", "label": "Insider flow balance", "raw": -1.0, "unit": "ratio"},
                {"key": "congress", "label": "Congress flow balance", "raw": None, "unit": "ratio"},
            ],
        },
        {
            "key": "options",
            "label": "Options positioning",
            "percentile": None,
            "raw": None,
            "rawLabel": "Options sentiment",
            "present": False,
        },
    ],
    "flags": [
        {"key": "clustered_insider_selling", "label": "Clustered insider selling", "active": False},
        {"key": "unusual_options_flow", "label": "Unusual options flow", "active": True},
    ],
    "disclaimer": DISCLAIMER,
}

# The same stock as served before the score fields shipped. Every one of the four is
# absent rather than null, which is the shape the optional typing exists for.
LEGACY_RATED_PAYLOAD = {
    k: v
    for k, v in RATED_PAYLOAD.items()
    if k
    not in (
        "score",
        "bucketLetter",
        "riskConditions",
        "riskAdjustments",
        "penaltyPoints",
    )
}
LEGACY_RATED_PAYLOAD["letter"] = "B"

NOT_RATED_PAYLOAD = {
    "ticker": "SPY",
    "kbEntityId": "kb/etf/3",
    "rated": False,
    "asOf": "2026-09-03",
    "reason": "not_rated_today",
    "dimensionsPresent": 0,
    "presentDimensions": [],
    "dimensions": [
        {
            "key": "crowd",
            "label": "Crowd sentiment",
            "percentile": None,
            "raw": None,
            "rawLabel": "7-day SentiSense Score",
            "present": False,
        },
        {
            "key": "smart_money",
            "label": "Smart money",
            "percentile": None,
            "raw": None,
            "rawLabel": None,
            "present": False,
        },
    ],
    "flags": [],
    "disclaimer": DISCLAIMER,
}


class TestRatedShape:
    def test_calls_the_rating_endpoint_and_uppercases_the_ticker(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(RATED_PAYLOAD)) as g:
            result = client.get_rating("aapl")
        assert "/api/v1/rating/AAPL" in g.call_args[0][0]
        assert isinstance(result, StockRating)

    def test_carries_the_headline_grade(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(RATED_PAYLOAD)):
            result = client.get_rating("AAPL")
        assert result.rated is True
        assert result.letter == "C"
        assert result.score == pytest.approx(59.5)
        assert result.percentile == pytest.approx(79.96146435452793)
        assert result.composite == pytest.approx(0.21454864250697855)
        # The rank's denominator. Without it a percentile is a number with no cohort.
        assert result.ratedCount == 1038
        assert result.methodologyVersion == "2026.09-v1"
        assert result.kbEntityId == "kb/company/1"

    def test_the_letter_is_the_served_one(self, client):
        # Stored, never re-derived here or upstream of here, so the bucket edges live in
        # exactly one place. A client that recomputes them drifts the day they move.
        with patch.object(client.session, "get", return_value=_mock_response(RATED_PAYLOAD)):
            result = client.get_rating("AAPL")
        assert result.letter == RATED_PAYLOAD["letter"]

    def test_a_rated_response_leaves_the_unrated_fields_empty(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(RATED_PAYLOAD)):
            result = client.get_rating("AAPL")
        assert result.reason is None
        assert result.dimensionsPresent is None
        assert result.presentDimensions == []

    def test_the_disclaimer_rides_along(self, client):
        # Every surface that shows a grade has to show this, so it must survive parsing.
        with patch.object(client.session, "get", return_value=_mock_response(RATED_PAYLOAD)):
            result = client.get_rating("AAPL")
        assert result.disclaimer == DISCLAIMER


class TestScoreAndRiskConditions:
    """The headline number, and the three fields that explain the gap under it.

    ``percentile`` is the rank of the blended signals. ``score`` is that rank less 12
    points per active risk condition, and ``letter`` is the band of ``score``. Reading
    the letter off the percentile therefore disagrees with the API for every stock that
    carries a condition, which is the mistake this class exists to catch.
    """

    def test_the_score_is_the_percentile_less_the_summed_adjustments(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(RATED_PAYLOAD)):
            result = client.get_rating("AAPL")
        assert result.score == pytest.approx(59.5)
        assert result.penaltyPoints == pytest.approx(20.5)
        # The total is the sum of the graded rows, not 12 times how many there are: a
        # condition can cost anything up to 12, and the second one here costs 8.5.
        assert result.penaltyPoints == pytest.approx(
            sum(a.points for a in result.riskAdjustments)
        )
        assert result.penaltyPoints != 12 * len(result.riskConditions)
        assert result.score == pytest.approx(result.percentile - result.penaltyPoints, abs=0.1)

    def test_each_adjustment_names_its_condition_and_its_cost(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(RATED_PAYLOAD)):
            result = client.get_rating("AAPL")
        assert all(isinstance(a, RiskAdjustment) for a in result.riskAdjustments)
        assert [(a.condition, a.points) for a in result.riskAdjustments] == [
            ("unprofitable", 12.0),
            ("high_leverage", 8.5),
        ]
        # Every graded row names a condition that is also listed as active.
        assert [a.condition for a in result.riskAdjustments] == result.riskConditions

    def test_the_letter_bands_the_score_not_the_percentile(self, client):
        # 79.9 would band as B. The two conditions take the score to 59.5, which bands as
        # C, and ``bucketLetter`` keeps the pre-penalty band visible next to it.
        with patch.object(client.session, "get", return_value=_mock_response(RATED_PAYLOAD)):
            result = client.get_rating("AAPL")
        assert result.letter == "C"
        assert result.bucketLetter == "B"
        assert result.letter != result.bucketLetter

    def test_the_active_conditions_are_named(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(RATED_PAYLOAD)):
            result = client.get_rating("AAPL")
        assert result.riskConditions == ["unprofitable", "high_leverage"]

    def test_an_older_response_still_parses(self, client):
        # The four fields are absent, not null, on anything served before they shipped.
        # Absent has to read as "not reported": None for the scalars, an empty list for
        # the conditions, never a zero that would look like a clean stock.
        with patch.object(
            client.session, "get", return_value=_mock_response(LEGACY_RATED_PAYLOAD)
        ):
            result = client.get_rating("AAPL")
        assert result.rated is True
        assert result.score is None
        assert result.bucketLetter is None
        assert result.penaltyPoints is None
        assert result.riskConditions == []
        assert result.riskAdjustments == []
        # Everything that was there before is untouched.
        assert result.letter == "B"
        assert result.percentile == pytest.approx(79.96146435452793)
        assert result.ratedCount == 1038
        assert len(result.dimensions) == 3

    def test_an_unrated_response_carries_none_of_them(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(NOT_RATED_PAYLOAD)):
            result = client.get_rating("SPY")
        assert result.score is None
        assert result.bucketLetter is None
        assert result.penaltyPoints is None
        assert result.riskConditions == []
        assert result.riskAdjustments == []


class TestDimensions:
    def test_dimensions_parse_into_models(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(RATED_PAYLOAD)):
            result = client.get_rating("AAPL")
        assert all(isinstance(d, RatingDimension) for d in result.dimensions)
        crowd = result.dimensions[0]
        assert crowd.key == "crowd"
        assert crowd.label == "Crowd sentiment"
        assert crowd.rawLabel == "7-day SentiSense Score"
        assert crowd.raw == pytest.approx(9.16962530776088)

    def test_an_absent_dimension_is_a_row_not_a_gap(self, client):
        # The row arrives with present=False and a None percentile. Substituting zero
        # would rank the dimension we know nothing about at the bottom of the market.
        with patch.object(client.session, "get", return_value=_mock_response(RATED_PAYLOAD)):
            result = client.get_rating("AAPL")
        options = [d for d in result.dimensions if d.key == "options"][0]
        assert options.present is False
        assert options.percentile is None
        assert options.raw is None

    def test_only_smart_money_carries_legs(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(RATED_PAYLOAD)):
            result = client.get_rating("AAPL")
        smart_money = [d for d in result.dimensions if d.key == "smart_money"][0]
        assert all(isinstance(leg, RatingSubLeg) for leg in smart_money.subLegs)
        assert [leg.key for leg in smart_money.subLegs] == ["inst_13f", "insider", "congress"]
        assert smart_money.subLegs[0].unit == "%"
        assert smart_money.subLegs[1].unit == "ratio"
        # A leg with no data reports None, not zero: a zero balance is a real reading.
        assert smart_money.subLegs[2].raw is None
        # Every other dimension omits the field entirely, which parses as no legs.
        assert result.dimensions[0].subLegs == []


class TestFlags:
    def test_flags_parse_and_keep_their_active_state(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(RATED_PAYLOAD)):
            result = client.get_rating("AAPL")
        assert all(isinstance(f, RatingFlag) for f in result.flags)
        by_key = {f.key: f for f in result.flags}
        assert by_key["unusual_options_flow"].active is True
        # An evaluated-and-not-triggered flag is present and inactive. A flag the run
        # could not evaluate is absent, so the two states stay distinguishable.
        assert by_key["clustered_insider_selling"].active is False


class TestNotRatedShape:
    def test_no_grade_is_a_normal_answer(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(NOT_RATED_PAYLOAD)):
            result = client.get_rating("SPY")
        assert result.rated is False
        assert result.reason == "not_rated_today"
        assert result.dimensionsPresent == 0
        assert result.presentDimensions == []

    def test_the_graded_fields_are_all_none(self, client):
        with patch.object(client.session, "get", return_value=_mock_response(NOT_RATED_PAYLOAD)):
            result = client.get_rating("SPY")
        assert result.letter is None
        assert result.percentile is None
        assert result.composite is None
        assert result.ratedCount is None
        assert result.methodologyVersion is None

    def test_the_composition_still_arrives(self, client):
        # An unrated stock still renders its composition card, so the dimensions, the
        # date and the disclaimer are carried on both shapes.
        with patch.object(client.session, "get", return_value=_mock_response(NOT_RATED_PAYLOAD)):
            result = client.get_rating("SPY")
        assert [d.key for d in result.dimensions] == ["crowd", "smart_money"]
        assert all(d.present is False for d in result.dimensions)
        assert result.asOf == "2026-09-03"
        assert result.disclaimer == DISCLAIMER

    def test_present_dimensions_names_the_ones_with_data(self, client):
        payload = dict(NOT_RATED_PAYLOAD)
        payload["dimensionsPresent"] = 2
        payload["presentDimensions"] = ["crowd", "analysts"]
        with patch.object(client.session, "get", return_value=_mock_response(payload)):
            result = client.get_rating("SPY")
        assert result.presentDimensions == ["crowd", "analysts"]


class TestErrors:
    def test_unknown_ticker_raises_not_found(self, client):
        response = _mock_response(
            {"error": "entity_not_found", "message": "Unknown ticker 'ZZZZ'."},
            status_code=404,
            reason="Not Found",
        )
        with patch.object(client.session, "get", return_value=response):
            with pytest.raises(NotFoundError):
                client.get_rating("ZZZZ")


class TestVocabulary:
    """The Rating is an informational rank, never a directive.

    Prose drifts, and one stray "buy" in a docstring turns a research signal into
    something that reads as advice. Gate it rather than trust a reviewer to catch it.
    """

    # Whole words, so "holds" and "alongside" are not false positives.
    FORBIDDEN = ("buy", "buys", "sell", "sells", "hold", "long", "avoid", "recommendation")

    def test_the_method_docstring_stays_non_directive(self):
        # Whitespace-collapsed, so a phrase that happens to wrap across two source
        # lines still reads as the phrase it is.
        doc = re.sub(r"\s+", " ", (SentiSenseClient.get_rating.__doc__ or "").lower())
        assert doc
        # The API's own disclaimer says the Rating is *not* a recommendation, so that
        # one word is only allowed inside the negation.
        assert "not a recommendation" in doc
        cleaned = doc.replace("not a recommendation", "")
        offenders = [w for w in self.FORBIDDEN if re.search(r"\b%s\b" % w, cleaned)]
        assert not offenders, "directive vocabulary in get_rating docstring: %s" % offenders

    def test_the_model_docstrings_carry_the_informational_framing(self):
        doc = re.sub(r"\s+", " ", (StockRating.__doc__ or "").lower())
        assert "informational" in doc
        assert "not a recommendation" in doc
