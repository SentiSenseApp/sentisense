"""Gate: every response model keeps the keys it does not declare.

A key the API adds before this package declares it must stay readable, at the top
level and inside every nested model, rather than vanish while parsing. The gate below
enumerates every ``APIModel`` subclass in ``sentisense.types``, builds a payload for it
mechanically from its type hints with a neutral unknown key at every model position,
and checks each position still answers for that key. A new model, or a new hand-written
``from_dict``, that drops unknown keys fails here.
"""

import copy
import dataclasses
import inspect
import pickle
import typing
from typing import Any, Dict, List, Tuple, TypeVar, Union
from unittest.mock import MagicMock, patch

import pytest

import sentisense.types as T
from sentisense import SentiSenseClient
from sentisense.types import PreviewResult, StockPrice, Story, StoryCluster

UNKNOWN = "zzUnknown"
MARKER = "zz-marker"
MAX_DEPTH = 5

MODELS = sorted(
    (
        obj
        for obj in vars(T).values()
        if inspect.isclass(obj)
        and issubclass(obj, T.APIModel)
        and obj is not T.APIModel
        and obj.__module__ == T.__name__
    ),
    key=lambda c: c.__name__,
)

# Models the payload builder cannot cover, each with a one-line reason. Keep it empty
# unless a model truly cannot be built from a payload.
EXCLUDED: Dict[str, str] = {}

# Names a model must never declare: the base class reads or exposes them, or (``data``)
# ``PreviewResult.data`` would shadow them.
RESERVED = {"extra_fields", T._EXTRA_ATTR, "get", "from_dict", "data"}


def _is_model(tp: Any) -> bool:
    return inspect.isclass(tp) and issubclass(tp, T.APIModel)


def _sample(tp: Any, depth: int, path: Tuple, expect: List[Tuple], typevars: Dict) -> Any:
    """A JSON-like value for ``tp``; records the path of every model position."""
    if isinstance(tp, typing.ForwardRef):
        # Python 3.8 leaves a quoted name nested in a generic unresolved.
        tp = vars(T)[tp.__forward_arg__]
    if isinstance(tp, TypeVar):
        bound = typevars.get(tp)
        if bound is None:
            # A generic slot with nothing bound: a bare object carrying the marker.
            expect.append(path)
            return {UNKNOWN: MARKER}
        tp = bound
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if origin is Union:
        return _sample(
            next(a for a in args if a is not type(None)), depth, path, expect, typevars
        )
    if origin in (list, List):
        return [_sample(args[0], depth, path + (0,), expect, typevars)] if args else []
    if origin in (dict, Dict):
        if args and args[1] is not Any:
            return {"k": _sample(args[1], depth, path + ("k",), expect, typevars)}
        return {}
    if origin is not None and _is_model(origin):
        params = getattr(origin, "__parameters__", ())
        return _payload(origin, depth, path, expect, dict(zip(params, args)))
    if _is_model(tp):
        return _payload(tp, depth, path, expect, {})
    if tp is bool:
        return True
    if tp is int:
        return 1
    if tp is float:
        return 1.5
    return "x"


def _payload(cls: type, depth: int, path: Tuple, expect: List[Tuple], typevars: Dict) -> Dict:
    expect.append(path)
    payload: Dict[str, Any] = {UNKNOWN: MARKER}
    if depth >= MAX_DEPTH:
        return payload
    hints = typing.get_type_hints(cls)
    for name in cls.__dataclass_fields__:
        payload[name] = _sample(hints[name], depth + 1, path + (name,), expect, typevars)
    return payload


def _node_at(obj: Any, path: Tuple) -> Any:
    node = obj
    for step in path:
        node = getattr(node, step) if isinstance(node, T.APIModel) else node[step]
    return node


def _assert_keeps_unknown(node: Any, where: str) -> None:
    if isinstance(node, T.APIModel):
        assert node.get(UNKNOWN) == MARKER, where
        assert node[UNKNOWN] == MARKER, where
        assert UNKNOWN in node, where
        assert getattr(node, UNKNOWN) == MARKER, where
        assert node.extra_fields.get(UNKNOWN) == MARKER, where
        assert not set(node.extra_fields) & set(type(node).__dataclass_fields__), where
    else:
        # A nested value the model keeps as a plain dict passes every key through.
        assert isinstance(node, dict) and node.get(UNKNOWN) == MARKER, where


class TestEnumeration:
    def test_the_gate_sees_the_models(self):
        assert len(MODELS) > 100, "model enumeration broke; the gate is not running"

    def test_every_dataclass_in_types_is_an_api_model(self):
        # A plain dataclass would have no from_dict and no extras at all.
        plain = [
            name
            for name, obj in vars(T).items()
            if inspect.isclass(obj)
            and dataclasses.is_dataclass(obj)
            and obj.__module__ == T.__name__
            and not issubclass(obj, T.APIModel)
        ]
        assert not plain

    def test_exclusions_name_real_models(self):
        names = {m.__name__ for m in MODELS}
        assert set(EXCLUDED) <= names

    @pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
    def test_no_model_declares_a_reserved_name(self, model):
        assert not RESERVED & set(model.__dataclass_fields__)

    def test_storage_attribute_is_private(self):
        # Attribute access never answers a private name from the response, so the
        # storage name cannot be confused with a response key.
        assert T._EXTRA_ATTR.startswith("_")


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
def test_unknown_keys_survive_parsing_at_every_level(model):
    if model.__name__ in EXCLUDED:
        pytest.skip(EXCLUDED[model.__name__])
    expect: List[Tuple] = []
    payload = _payload(model, 0, (), expect, {})
    obj = model.from_dict(payload)
    assert isinstance(obj, model)
    assert expect and expect[0] == ()
    for path in expect:
        _assert_keeps_unknown(_node_at(obj, path), "%s at %r" % (model.__name__, path))


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
def test_a_payload_without_unknown_keys_adds_no_state(model):
    obj = model.from_dict({})
    assert T._EXTRA_ATTR not in vars(obj)
    assert dict(obj.extra_fields) == {}


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
def test_constructor_built_objects_behave_as_before(model):
    obj = model()
    assert T._EXTRA_ATTR not in vars(obj)
    assert dict(obj.extra_fields) == {}
    assert not hasattr(obj, "nope")
    assert "nope" not in obj
    assert obj.get("nope") is None
    assert obj.get("nope", 7) == 7
    with pytest.raises(AttributeError):
        obj["nope"]
    with pytest.raises(AttributeError):
        obj.nope


class TestAccessRules:
    def test_declared_fields_win(self):
        price = StockPrice.from_dict({"ticker": "AAPL", "currentPrice": 1.0, UNKNOWN: 2})
        assert price.ticker == "AAPL" and price["ticker"] == "AAPL"
        assert dict(price.extra_fields) == {UNKNOWN: 2}

    def test_a_key_named_like_a_method_is_readable_dict_style(self):
        price = StockPrice.from_dict({"get": "g", "extra_fields": "e", "from_dict": "f"})
        assert price["get"] == "g" and price.get("get") == "g"
        assert callable(price.get)
        assert price["extra_fields"] == "e"
        assert price.extra_fields["extra_fields"] == "e"
        assert price["from_dict"] == "f"

    def test_private_and_dunder_keys_are_dict_style_only(self):
        price = StockPrice.from_dict({"_hidden": 1, "__odd__": 2})
        assert price["_hidden"] == 1 and price.get("__odd__") == 2
        assert "_hidden" in price and "__odd__" in price
        assert not hasattr(price, "_hidden")
        with pytest.raises(AttributeError):
            getattr(price, "__odd__")

    def test_extra_fields_is_read_only(self):
        price = StockPrice.from_dict({UNKNOWN: 1})
        with pytest.raises(TypeError):
            price.extra_fields[UNKNOWN] = 2  # type: ignore[index]
        assert price.get(UNKNOWN) == 1

    def test_equality_and_repr_stay_field_based(self):
        a = StockPrice.from_dict({"ticker": "AAPL", UNKNOWN: 1})
        b = StockPrice.from_dict({"ticker": "AAPL"})
        assert a == b
        assert UNKNOWN not in repr(a)
        assert dataclasses.asdict(a) == dataclasses.asdict(b)

    def test_a_half_built_object_does_not_recurse(self):
        obj = StockPrice.__new__(StockPrice)
        assert not hasattr(obj, "nope")
        assert obj.get("nope") is None
        with pytest.raises(AttributeError):
            obj["nope"]
        with pytest.raises(AttributeError):
            obj.__deepcopy__


def _story() -> Story:
    return Story.from_dict({
        "id": "c1",
        "tickers": ["EXMP"],
        UNKNOWN: "top",
        "cluster": {"id": "c1", "title": "t", "clusteredAt": 1757001600, UNKNOWN: "nested"},
    })


class TestCopyAndPickle:
    @pytest.mark.parametrize(
        "clone", [copy.copy, copy.deepcopy, lambda o: pickle.loads(pickle.dumps(o))],
        ids=["copy", "deepcopy", "pickle"],
    )
    def test_extras_survive(self, clone):
        restored = clone(_story())
        assert restored == _story()
        assert restored.get(UNKNOWN) == "top"
        assert restored.cluster[UNKNOWN] == "nested"
        assert getattr(restored.cluster, UNKNOWN) == "nested"

    def test_constructor_built_object_round_trips_unchanged(self):
        cluster = StoryCluster(id="c1", title="t")
        restored = pickle.loads(pickle.dumps(cluster))
        assert restored == cluster
        assert T._EXTRA_ATTR not in vars(restored)
        assert not hasattr(restored, "nope")


class TestPreviewResultPassThrough:
    def _result(self) -> PreviewResult:
        client = SentiSenseClient("test-api-key")
        return client._unwrap(
            {"isPreview": False, "previewReason": None,
             "data": {"inflows": [{"ticker": "AAPL", UNKNOWN: 5}], UNKNOWN: "top"}},
            item_cls=T.InstitutionalFlows,
        )

    def test_all_four_access_paths_reach_the_payload(self):
        result = self._result()
        assert result[UNKNOWN] == "top"
        assert result.get(UNKNOWN) == "top"
        assert UNKNOWN in result
        assert getattr(result, UNKNOWN) == "top"
        assert dict(result.extra_fields) == {UNKNOWN: "top"}
        assert result.inflows[0].get(UNKNOWN) == 5

    def test_membership_on_other_payloads(self):
        assert "x" not in PreviewResult(None, False, None)
        assert 2 in PreviewResult([1, 2], False, None)
        assert "k" in PreviewResult({"k": 1}, False, None)
        assert "missing" not in self._result()

    def test_through_a_client_method(self):
        client = SentiSenseClient("test-api-key")
        response = MagicMock(status_code=200, ok=True)
        response.json.return_value = {
            "isPreview": False,
            "previewReason": None,
            "data": {
                "asOf": 1,
                "reported": {"rows": [{"ticker": "AAPL", UNKNOWN: 1}], UNKNOWN: 2},
                "upcoming": {"rows": []},
            },
        }
        with patch.object(client.session, "get", return_value=response):
            ranked = client.get_ranked_earnings()
        assert ranked.reported.rows[0][UNKNOWN] == 1
        assert ranked.reported.get(UNKNOWN) == 2
