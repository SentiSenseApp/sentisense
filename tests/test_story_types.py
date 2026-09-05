"""Unit tests for the story cluster provenance fields.

Two contracts are gated here because both fail quietly rather than loudly:

* ``storySource`` and ``isLive`` are parsed off the cluster summary. The base
  ``from_dict`` drops keys it does not know, so a field added to the wire but not to
  the dataclass disappears with no error and reads as "the API does not send it".
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
