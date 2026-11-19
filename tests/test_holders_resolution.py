"""Unit tests for the fields ``get_stock_holders`` reads from the response envelope.

Contracts gated here:

* ``requested_ticker``, ``resolution`` and ``stored_ticker`` come from the envelope keys
  ``requestedTicker``, ``resolution`` and ``storedTicker``, and read ``None`` when the
  response does not carry them.
* The security answered for has one name, the payload's ``ticker``. The envelope's copy
  of that value is not exposed under any name.
* Everything else reads as on a plain ``PreviewResult``: the payload by item and by
  attribute (except a payload key named like one of the three fields, which is read by
  item), the preview metadata, positional construction and restored pickles.
"""

import pickle
from unittest.mock import MagicMock, patch

import pytest

import sentisense
from sentisense import DossierAllowance, PreviewResult, SentiSenseClient, StockHoldersResult

HOLDERS = {
    "ticker": "GOOG",
    "reportDate": "2025-12-31",
    "holderCount": 2,
    "holders": [
        {"institutionName": "Example Capital", "shares": 1000, "valueUsd": 190000},
        {"institutionName": "Sample Partners", "shares": 500, "valueUsd": 95000},
    ],
}

# The shape the API answers GOOG with: the Class C roster, resolved as a share class.
SHARE_CLASS_ENVELOPE = {
    "isPreview": False,
    "previewReason": None,
    "totalCount": 2,
    "data": HOLDERS,
    "requestedTicker": "GOOG",
    "resolvedTicker": "GOOG",
    "resolution": "share_class",
    "storedTicker": "GOOG",
}

SPELLING_PREVIEW_ENVELOPE = {
    "isPreview": True,
    "previewReason": "PRO_REQUIRED",
    "totalCount": 6000,
    "upgrade": {"plan": "PRO", "message": "Upgrade for every holder."},
    "data": dict(HOLDERS, ticker="BRK.B"),
    "requestedTicker": "BRKB",
    "resolvedTicker": "BRK.B",
    "resolution": "spelling",
    "storedTicker": "BRKB",
}


@pytest.fixture
def client():
    return SentiSenseClient("test-api-key")


def _holders(client, envelope, ticker="GOOG", **kwargs):
    resp = MagicMock()
    resp.status_code = 200
    resp.ok = True
    resp.json.return_value = envelope
    with patch.object(SentiSenseClient, "_get", return_value=resp) as get:
        result = client.get_stock_holders(ticker, **kwargs)
    return result, get


class TestEnvelopeFields:
    def test_share_class_envelope(self, client):
        result, get = _holders(client, SHARE_CLASS_ENVELOPE)
        get.assert_called_once_with("/api/v1/institutional/holders/GOOG", params={})
        assert isinstance(result, StockHoldersResult) and isinstance(result, PreviewResult)
        assert result.requested_ticker == "GOOG"
        assert result.resolution == "share_class"
        assert result.stored_ticker == "GOOG"
        assert result.is_preview is False and result.total_count == 2

    def test_spelling_preview_keeps_the_preview_metadata(self, client):
        result, _ = _holders(client, SPELLING_PREVIEW_ENVELOPE, ticker="brkb", limit=5)
        assert (result.requested_ticker, result.resolution, result.stored_ticker) == ("BRKB", "spelling", "BRKB")
        assert result.is_preview is True
        assert result.preview_reason == "PRO_REQUIRED"
        assert result.total_count == 6000
        assert result.upgrade == {"plan": "PRO", "message": "Upgrade for every holder."}
        assert result["ticker"] == "BRK.B"

    def test_a_response_without_the_keys_reads_none(self, client):
        envelope = {"isPreview": False, "previewReason": None, "data": HOLDERS}
        result, _ = _holders(client, envelope)
        assert isinstance(result, StockHoldersResult)
        assert result.requested_ticker is None
        assert result.resolution is None
        assert result.stored_ticker is None

    def test_null_values_read_none(self, client):
        envelope = dict(SHARE_CLASS_ENVELOPE, requestedTicker=None, resolution=None, storedTicker=None)
        result, _ = _holders(client, envelope)
        assert (result.requested_ticker, result.resolution, result.stored_ticker) == (None, None, None)

    def test_an_empty_payload_still_carries_the_fields(self, client):
        envelope = dict(SHARE_CLASS_ENVELOPE, data={}, totalCount=None)
        result, _ = _holders(client, envelope)
        assert result.data == {} and not result
        assert result.resolution == "share_class"


class TestPayloadAccessIsUnchanged:
    def test_item_and_attribute_access_read_the_payload(self, client):
        result, _ = _holders(client, SHARE_CLASS_ENVELOPE)
        assert result.data == HOLDERS
        assert result["ticker"] == "GOOG" and result.ticker == "GOOG"
        assert result["holders"] == HOLDERS["holders"] and result.holders == HOLDERS["holders"]
        assert result.holderCount == 2
        assert "holders" in result and "requestedTicker" not in result
        assert len(result) == len(HOLDERS) and set(result) == set(HOLDERS)

    def test_a_payload_key_spelled_like_a_new_field_stays_in_the_payload(self, client):
        envelope = dict(SHARE_CLASS_ENVELOPE, data=dict(HOLDERS, resolution="payload"))
        result, _ = _holders(client, envelope)
        assert result.resolution == "share_class"
        assert result["resolution"] == "payload"


class TestOneNameForTheSecurity:
    @pytest.mark.parametrize("name", ["resolved_ticker", "resolvedTicker"])
    def test_no_attribute_carries_the_envelope_copy(self, client, name):
        result, _ = _holders(client, SHARE_CLASS_ENVELOPE)
        assert not hasattr(result, name)
        assert name not in dir(result)
        assert name not in vars(result)
        assert name not in vars(StockHoldersResult)

    @pytest.mark.parametrize("name", ["resolved_ticker", "resolvedTicker"])
    def test_no_docstring_names_it(self, name):
        assert name not in (StockHoldersResult.__doc__ or "")
        assert name not in (SentiSenseClient.get_stock_holders.__doc__ or "")
        assert name not in (StockHoldersResult.__init__.__doc__ or "")

    def test_the_payload_ticker_is_the_security_answered_for(self, client):
        result, _ = _holders(client, SPELLING_PREVIEW_ENVELOPE, ticker="BRKB")
        assert result.ticker == "BRK.B"
        assert result.stored_ticker == "BRKB"


class TestConstructionAndPickles:
    def _full(self, cls=PreviewResult):
        return cls({"k": 1}, False, None, 3, {"plan": "PRO"}, True, DossierAllowance(10, 4, 1793505600))

    @pytest.mark.parametrize("cls", [PreviewResult, StockHoldersResult])
    def test_positional_construction_is_the_preview_result_order(self, cls):
        result = self._full(cls)
        assert result.data == {"k": 1}
        assert (result.is_preview, result.preview_reason, result.total_count) == (False, None, 3)
        assert result.upgrade == {"plan": "PRO"}
        assert result.sample_company is True
        assert result.dossier_allowance == DossierAllowance(10, 4, 1793505600)

    def test_the_new_fields_are_keyword_only(self):
        with pytest.raises(TypeError):
            StockHoldersResult({}, False, None, None, None, None, None, "GOOG")  # type: ignore[misc]
        result = StockHoldersResult({}, False, None, requested_ticker="GOOG", resolution="exact",
                                    stored_ticker="GOOG")
        assert (result.requested_ticker, result.resolution, result.stored_ticker) == ("GOOG", "exact", "GOOG")
        assert result.total_count is None and result.dossier_allowance is None

    def test_a_pickle_round_trip_keeps_everything(self, client):
        result, _ = _holders(client, SHARE_CLASS_ENVELOPE)
        restored = pickle.loads(pickle.dumps(result))
        assert isinstance(restored, StockHoldersResult)
        assert (restored.requested_ticker, restored.resolution, restored.stored_ticker) == (
            "GOOG", "share_class", "GOOG",
        )
        assert restored.total_count == 2 and restored["ticker"] == "GOOG"

    @pytest.mark.parametrize("name", ["requested_ticker", "resolution", "stored_ticker"])
    def test_a_restored_object_without_a_field_reads_none(self, client, name):
        result, _ = _holders(client, SHARE_CLASS_ENVELOPE)
        delattr(result, name)
        restored = pickle.loads(pickle.dumps(result))
        assert getattr(restored, name) is None
        assert restored["ticker"] == "GOOG"

    def test_a_plain_preview_result_is_unchanged(self):
        result = self._full()
        for name in ("total_count", "upgrade", "sample_company", "dossier_allowance"):
            delattr(result, name)
        restored = pickle.loads(pickle.dumps(result))
        assert restored.total_count is None and restored.dossier_allowance is None
        assert restored.k == 1 and restored["k"] == 1
        assert not hasattr(PreviewResult, "requested_ticker")
        assert not hasattr(restored, "stored_ticker")


def test_the_result_class_is_exported():
    assert "StockHoldersResult" in sentisense.__all__
    assert sentisense.StockHoldersResult is StockHoldersResult


def test_holders_history_is_unchanged(client):
    resp = MagicMock()
    resp.status_code = 200
    resp.ok = True
    resp.json.return_value = {"isPreview": False, "previewReason": None, "data": {"ticker": "GOOG", "quarters": []}}
    with patch.object(SentiSenseClient, "_get", return_value=resp):
        history = client.get_stock_holders_history("GOOG")
    assert type(history) is PreviewResult
