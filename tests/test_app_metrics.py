"""The four App Store metric types are plain ``get_metrics`` names.

Nothing in the client enumerates metric types (``metric_type`` is a free string), so what
can drift is the documentation: the docstring a caller reads in an editor and the README
line a reader sees first. Gate both against one list, and gate the request path.
"""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sentisense import SentiSenseClient

README = Path(__file__).resolve().parent.parent / "README.md"

APP_METRICS = [
    "app_review_count",
    "app_rating",
    "app_all_ratings_count",
    "app_all_ratings_avg",
]


@pytest.fixture
def client():
    return SentiSenseClient("test-api-key")


def _mock_response(json_data):
    resp = MagicMock()
    resp.status_code = 200
    resp.ok = True
    resp.reason = "OK"
    resp.json.return_value = json_data
    return resp


class TestAppMetricRequests:
    @pytest.mark.parametrize("metric_type", APP_METRICS)
    @patch.object(SentiSenseClient, "_get")
    def test_get_metrics_uses_the_metric_path(self, mock_get, client, metric_type):
        mock_get.return_value = _mock_response([])
        client.get_metrics("Instagram", metric_type=metric_type)
        mock_get.assert_called_once_with(
            f"/api/v2/metrics/entity/Instagram/metric/{metric_type}",
            params={},
        )

    @patch.object(SentiSenseClient, "_get")
    def test_points_are_returned_as_served(self, mock_get, client):
        # Trimmed live shapes with synthetic numbers: a count nests its scalar at
        # metricValue.value, an average one level deeper, and both carry the flat value.
        count = {
            "timestamp": 1760000000000,
            "metricType": "APP_ALL_RATINGS_COUNT",
            "metricValue": {"type": "CountMetricValue", "value": 1200, "count": 1200},
            "value": 1200.0,
        }
        average = {
            "timestamp": 1760000000000,
            "metricType": "APP_ALL_RATINGS_AVG",
            "metricValue": {
                "type": "ValueMetricValue",
                "value": {"valueType": "double", "value": 4.5},
                "valueType": "MEAN",
            },
            "value": 4.5,
        }
        mock_get.return_value = _mock_response([count])
        assert client.get_metrics("Instagram", metric_type="app_all_ratings_count")[0]["value"] == 1200
        mock_get.return_value = _mock_response([average])
        points = client.get_metrics("Instagram", metric_type="app_all_ratings_avg")
        assert points[0]["value"] == 4.5
        assert points[0]["metricValue"]["value"]["value"] == 4.5


class TestAppMetricDocs:
    def test_docstring_names_every_app_metric(self):
        doc = SentiSenseClient.get_metrics.__doc__ or ""
        missing = [m for m in APP_METRICS if f'"{m}"' not in doc]
        assert not missing, "get_metrics docstring is missing: %s" % missing

    def test_readme_metric_types_line_names_every_app_metric(self):
        readme = README.read_text(encoding="utf-8")
        line = next((l for l in readme.splitlines() if l.startswith("Metric types are ")), "")
        assert line, "README no longer has a 'Metric types are' line; update this test"
        missing = [m for m in APP_METRICS if f"`{m}`" not in line]
        assert not missing, "README metric types line is missing: %s" % missing
