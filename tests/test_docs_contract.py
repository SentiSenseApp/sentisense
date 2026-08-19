"""Mechanical gates on the documentation that ships with the wheel.

Every check here corresponds to something the README or a docstring got wrong while
the code was right. Prose drifts silently; a failing test does not. Keep new claims
about method names, argument defaults, or exception coverage gated here rather than
trusting a reviewer to notice the next time one of them moves.
"""

import dataclasses
import inspect
import re
from pathlib import Path

import pytest

from sentisense import SentiSenseClient
from sentisense.types import StockDetail
from sentisense.exceptions import (
    APIError,
    AuthenticationError,
    DeepHistoryUnavailable,
    NotFoundError,
    RateLimitError,
    SentiSenseError,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
SRC = REPO_ROOT / "src" / "sentisense"

# Every ``get_x(...)``/``list_x(...)`` reference in the README's method tables.
_METHOD_CELL = re.compile(r"^\| `([a-z_][a-z0-9_]*)\(", re.MULTILINE)


@pytest.fixture(scope="module")
def readme() -> str:
    return README.read_text(encoding="utf-8")


class TestReadmeMethodTables:
    def test_every_documented_method_exists(self, readme):
        documented = set(_METHOD_CELL.findall(readme))
        assert documented, "method tables did not parse; the regex needs updating"
        missing = sorted(m for m in documented if not hasattr(SentiSenseClient, m))
        assert not missing, (
            "README documents methods the client does not have: %s" % missing
        )

    def test_get_story_is_not_advertised(self, readme):
        # The single-story endpoint is deliberately not wrapped. It was listed in the
        # method table for several releases and raised AttributeError on every call.
        assert not hasattr(SentiSenseClient, "get_story")
        assert "`get_story(" not in readme

    def test_unwrapped_endpoints_are_listed_as_such(self, readme):
        section = readme.split("## Not yet in the Python SDK", 1)[1]
        assert "/api/v1/documents/stories/{clusterId}" in section
        # get_stock_entities has shipped since 0.30.0, so its endpoint must not still
        # be advertised as unavailable.
        assert "/api/v1/stocks/{ticker}/entities" not in section
        assert hasattr(SentiSenseClient, "get_stock_entities")
        # Same for the report endpoint, wrapped since 0.35.0.
        assert "/api/v1/stocks/{ticker}/ai-summary" not in section
        assert hasattr(SentiSenseClient, "get_stock_ai_summary")


class TestReadmeCodeSamples:
    """The runnable snippets, not just the method tables.

    The tables were gated from the start; the Quick Start was not, so a snippet could
    call a method that never existed and the suite stayed green. Anything a reader can
    paste has to resolve.
    """

    def test_every_client_call_in_a_snippet_exists(self, readme):
        fences = re.findall(r"```python\n(.*?)```", readme, re.DOTALL)
        assert fences, "no python fences parsed; the regex needs updating"
        called = sorted(
            {m for f in fences for m in re.findall(r"client\.([a-z_][a-z0-9_]*)\(", f)}
        )
        assert called, "no client calls parsed; the regex needs updating"
        missing = [c for c in called if not hasattr(SentiSenseClient, c)]
        assert not missing, "README snippets call methods that do not exist: %s" % missing

    def test_quick_start_opens_on_the_tracked_universe(self, readme):
        # A reader's first question is which tickers are covered, so the universe call
        # leads the Quick Start rather than sitting in a table halfway down.
        quick_start = readme.split("## Quick Start", 1)[1].split("## Authentication", 1)[0]
        assert "get_all_stocks()" in quick_start
        assert "get_all_stocks_detailed()" in quick_start


class TestMetricTypeNames:
    """One spelling of the Score, in the README and the docstrings alike.

    The server accepts "sentisense" as well as "sentisense_score", so a caller copying
    either one works and no runtime error ever reveals the disagreement. That is exactly
    the drift a reader has to resolve by guessing, so the docs pick the canonical name
    the API echoes back in ``metricType``.
    """

    CANONICAL = "sentisense_score"

    def test_readme_documents_the_canonical_name(self, readme):
        assert self.CANONICAL in readme

    @pytest.mark.parametrize("method", ["get_metrics", "get_metrics_distribution"])
    def test_docstring_uses_the_canonical_name(self, method):
        doc = getattr(SentiSenseClient, method).__doc__ or ""
        assert self.CANONICAL in doc
        assert '"sentisense"' not in doc


class TestStockDetailShapeDocs:
    """The README promises company names on the detailed universe, so they must arrive.

    Live shape on /api/v1/stocks/detailed: ticker, simpleName, companyName, kbEntityId,
    urlSlug, brandColor, socialDominance. It never sends ``name``, which is why the model
    used to hand back an empty string for every row.
    """

    def test_the_model_carries_both_name_fields(self):
        fields = {f.name for f in dataclasses.fields(StockDetail)}
        assert {"simpleName", "companyName"} <= fields

    def test_name_falls_back_to_simple_name(self):
        detail = StockDetail.from_dict(
            {"ticker": "A", "simpleName": "Agilent", "companyName": "Agilent Technologies, Inc."}
        )
        assert detail.name == "Agilent"


class TestReadmeArgumentDefaults:
    """A documented default that disagrees with the signature is a trap, not a typo."""

    @pytest.mark.parametrize(
        "method, argument",
        [
            ("get_metrics", "metric_type"),
            ("get_metrics_distribution", "metric_type"),
            ("get_metrics_distribution", "dimension"),
            ("get_institutional_flows", "limit"),
            ("get_analyst_actions", "lookback_days"),
            ("get_analyst_market_activity", "lookback_days"),
            ("get_etf_insider_aggregate", "lookback_days"),
        ],
    )
    def test_documented_default_matches_the_signature(self, readme, method, argument):
        default = inspect.signature(getattr(SentiSenseClient, method)).parameters[
            argument
        ].default
        rendered = '"%s"' % default if isinstance(default, str) else str(default)
        rows = [line for line in readme.splitlines() if "`%s(" % method in line]
        assert rows, "README does not document %s" % method
        for row in rows:
            assert "%s=%s" % (argument, rendered) in row, (
                "README row for %s shows a different %s default than the code (%s)"
                % (method, argument, rendered)
            )


class TestReadmeExceptionTable:
    """The table reads as exhaustive, so anything the SDK can raise has to be in it."""

    def test_every_public_exception_is_listed(self, readme):
        section = readme.split("| Exception | HTTP Status |", 1)[1]
        for exc in (
            AuthenticationError,
            NotFoundError,
            RateLimitError,
            DeepHistoryUnavailable,
            APIError,
        ):
            assert "`%s`" % exc.__name__ in section, "%s is missing" % exc.__name__

    def test_deep_history_is_a_sentisense_error(self):
        assert issubclass(DeepHistoryUnavailable, SentiSenseError)


class TestHouseStyle:
    """No em dashes in anything that ships or renders on PyPI."""

    @pytest.mark.parametrize(
        "relative",
        ["README.md", "src/sentisense/client.py", "src/sentisense/types.py",
         "src/sentisense/exceptions.py", "src/sentisense/__init__.py"],
    )
    def test_no_em_dashes(self, relative):
        text = (REPO_ROOT / relative).read_text(encoding="utf-8")
        offenders = [
            "%s:%d" % (relative, i)
            for i, line in enumerate(text.splitlines(), 1)
            if "—" in line
        ]
        assert not offenders, "em dashes found at %s" % offenders


class TestChartAdjustmentDocs:
    """The split/dividend adjustment boundary sits at 10Y, not 5Y.

    Sampled live on two tickers with very different payout rates: 5Y weekly closes
    match the unadjusted daily series exactly, while 10Y and MAX carry a discount
    that grows with age and yield.
    """

    def test_docstring_puts_the_boundary_at_10y(self):
        doc = SentiSenseClient.get_stock_chart.__doc__ or ""
        assert '"10Y" and "MAX" are split- and dividend-adjusted' in doc
        assert '"5Y" and longer' not in doc

    def test_docstring_names_5y_as_split_only(self):
        doc = SentiSenseClient.get_stock_chart.__doc__ or ""
        assert "split-adjusted only" in doc
        assert '"5Y" included' in doc


class TestSentimentUnitDocs:
    def test_mention_share_is_not_promised_to_sum_to_100(self):
        # Sampled live across 7 tickers: 3 summed to 101, 4 to 100. The shares are
        # rounded per source, so an exact-100 promise is wrong.
        doc = SentiSenseClient.get_stock_sentiment.__doc__ or ""
        assert "sums to 100" not in doc
        assert "about 100" in doc
        assert "rounded" in doc


class TestEntityShapeDocs:
    def test_docstring_names_the_fields_the_wire_actually_sends(self):
        # Live shape on AAPL / NVDA / JPM: id, displayName, type, relatedStock,
        # urlSlug, title, category, iconUrl. It never sends entityId or name.
        doc = SentiSenseClient.get_stock_entities.__doc__ or ""
        for field in ("``id``", "``displayName``", "``relatedStock``", "``urlSlug``"):
            assert field in doc
        assert "``entityId``" not in doc
