"""Unit tests for the story cluster provenance fields.

Two contracts are gated here because both fail quietly rather than loudly:

* ``storySource`` and ``isLive`` are parsed off the cluster summary as declared
  fields. A key the dataclass does not declare is kept only as an untyped extra, so a
  field missing from the dataclass would lose its type and its documentation.
* Both are optional. An API build that predates them omits them, and the payload must
  still parse, with the fields reading ``None`` rather than defaulting to ``"AI"`` or
  ``False``. A caller that sees ``False`` cannot tell "not live" from "not known".

The payloads are trimmed copies of live responses.
"""

from sentisense.types import Story, StoryCluster

_LIST_ENTRY = {
    "id": "cluster-abc123",
    "clusterId": "cluster-abc123",
    "cluster": {
        "id": "cluster-abc123",
        "title": "Chipmaker lifts full-year outlook after a beat",
        "createdAt": 1757001600000,
        "clusteredAt": 1757001600,
        "clusterSize": 7,
        "averageSentiment": 0.42,
        "storySource": "ORIGINAL",
        "isLive": True,
    },
    "displayTickers": ["Example Corp (EXMP)"],
    "tickers": ["EXMP"],
    "primaryEntityNames": ["Example Corp"],
    "impactScore": 0.81,
    "brokeAt": 1757000400,
}


class TestStoryProvenanceFields:
    def test_fields_are_parsed_off_the_cluster(self):
        story = Story.from_dict(_LIST_ENTRY)
        assert story.cluster.storySource == "ORIGINAL"
        assert story.cluster.isLive is True

    def test_pipeline_story_reads_as_ai_and_not_live(self):
        payload = dict(_LIST_ENTRY)
        payload["cluster"] = dict(_LIST_ENTRY["cluster"], storySource="AI", isLive=False)
        story = Story.from_dict(payload)
        assert story.cluster.storySource == "AI"
        assert story.cluster.isLive is False

    def test_absent_fields_read_as_none_not_as_a_value(self):
        # What an API build that predates the fields answers. None has to survive as
        # "not known": collapsing it to False would make an unsettled story look settled.
        cluster = dict(_LIST_ENTRY["cluster"])
        del cluster["storySource"]
        del cluster["isLive"]
        story = Story.from_dict(dict(_LIST_ENTRY, cluster=cluster))
        assert story.cluster.storySource is None
        assert story.cluster.isLive is None

    def test_cluster_parses_standalone(self):
        cluster = StoryCluster.from_dict(_LIST_ENTRY["cluster"])
        assert cluster.storySource == "ORIGINAL"
        assert cluster.isLive is True
        assert cluster.clusteredAt == 1757001600

    def test_dict_style_access_reaches_the_new_fields(self):
        # The models advertise dict-style access alongside attributes; a field that
        # only answers one of the two is half-added.
        cluster = StoryCluster.from_dict(_LIST_ENTRY["cluster"])
        assert cluster["storySource"] == "ORIGINAL"
        assert cluster.get("isLive") is True


class TestStoryId:
    """``id`` is the story id; the deprecated ``clusterId`` is a copy of it."""

    def test_both_names_hold_the_id(self):
        story = Story.from_dict(_LIST_ENTRY)
        assert story.id == story.clusterId == story.cluster.id == "cluster-abc123"

    def test_deprecated_name_still_works_when_the_response_omits_it(self):
        payload = {k: v for k, v in _LIST_ENTRY.items() if k != "clusterId"}
        story = Story.from_dict(payload)
        assert story.id == "cluster-abc123"
        assert story.clusterId == "cluster-abc123"

    def test_deprecated_name_is_not_read_from_the_response(self):
        # Whatever the response says under the old name, the model answers with ``id``.
        story = Story.from_dict(dict(_LIST_ENTRY, clusterId="something-else"))
        assert story.clusterId == story.id == "cluster-abc123"

    def test_id_falls_back_to_the_cluster_summary(self):
        payload = {k: v for k, v in _LIST_ENTRY.items() if k not in ("id", "clusterId")}
        story = Story.from_dict(payload)
        assert story.id == story.clusterId == "cluster-abc123"

    def test_old_name_alone_does_not_supply_an_id(self):
        payload = {k: v for k, v in _LIST_ENTRY.items() if k not in ("id", "cluster")}
        story = Story.from_dict(payload)
        assert story.id is None and story.clusterId is None

    def test_no_id_anywhere_stays_none(self):
        payload = {k: v for k, v in _LIST_ENTRY.items() if k not in ("id", "clusterId", "cluster")}
        story = Story.from_dict(payload)
        assert story.id is None and story.clusterId is None
