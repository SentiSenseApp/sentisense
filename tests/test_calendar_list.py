"""Unit tests for ``list_calendars``, the calendar family's discovery list."""

import dataclasses
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sentisense import CalendarListing, CalendarListResponse, PreviewResult, SentiSenseClient

FIXTURES = Path(__file__).resolve().parent / "fixtures"

LIVE = json.loads((FIXTURES / "calendar_list_live.json").read_text())


@pytest.fixture
def client():
    return SentiSenseClient("test-api-key")


def _mock_response(json_data):
    resp = MagicMock()
    resp.status_code = 200
    resp.ok = True
    resp.json.return_value = json_data
    return resp


@patch.object(SentiSenseClient, "_get")
def test_path_and_no_params(mock_get, client):
    mock_get.return_value = _mock_response(LIVE)
    client.list_calendars()
    mock_get.assert_called_once_with("/api/v1/calendar")


@patch.object(SentiSenseClient, "_get")
def test_parses_the_live_list(mock_get, client):
    mock_get.return_value = _mock_response(LIVE)
    result = client.list_calendars()

    assert isinstance(result, CalendarListResponse)
    assert not isinstance(result, PreviewResult)
    assert len(result.calendars) == 1
    earnings = result.calendars[0]
    assert isinstance(earnings, CalendarListing)
    assert earnings.type == "earnings"
    assert earnings.path == "/api/v1/calendar/earnings"
    assert earnings.description


@patch.object(SentiSenseClient, "_get")
def test_every_wire_key_is_declared(mock_get, client):
    mock_get.return_value = _mock_response(LIVE)
    result = client.list_calendars()
    declared = {f.name for f in dataclasses.fields(CalendarListing)}
    assert set(LIVE) == {"calendars"}
    assert set(LIVE["calendars"][0]) <= declared
    assert dict(result.calendars[0].extra_fields) == {}


def test_the_listed_path_is_the_one_the_earnings_method_calls(client):
    with patch.object(SentiSenseClient, "_get") as mock_get:
        mock_get.return_value = _mock_response({"isPreview": False, "previewReason": None,
                                                "data": {"earnings": []}})
        client.get_earnings_calendar()
    assert mock_get.call_args[0][0] == LIVE["calendars"][0]["path"]


@pytest.mark.parametrize("body", [{}, {"calendars": None}, {"calendars": []}],
                         ids=["empty", "null", "no-rows"])
def test_empty_list(body):
    assert CalendarListResponse.from_dict(body).calendars == []


def test_undeclared_keys_are_kept():
    body = {"calendars": [dict(LIVE["calendars"][0], zzNew=2)], "zzNew": 1}
    result = CalendarListResponse.from_dict(body)
    assert result.get("zzNew") == 1
    assert result.calendars[0]["zzNew"] == 2
