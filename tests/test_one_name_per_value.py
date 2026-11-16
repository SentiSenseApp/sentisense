"""Gate: one value gets one name in the typed models.

A field whose comment or docstring says it is the "same value as" another field, or an
"alias of" or "alias for" one, gives a value the model already carries a second name.
Every typed field is a public name that callers come to depend on, so a second name for
the same value is kept only as a deliberate choice: an entry in ``ALLOWLIST`` below with
its reason. The scan reads ``src/sentisense/types.py`` as text, so it covers dataclass
models and ``TypedDict`` annotations alike.

Wording is attached to a field when it is a comment on the field's own line, a block of
comment lines directly above it, a string literal directly below it, or a sentence of the
class docstring that names the field.
"""

import ast
import io
import re
import tokenize
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

TYPES_PY = Path(__file__).resolve().parent.parent / "src" / "sentisense" / "types.py"

PHRASE = re.compile(r"same value as|alias (?:of|for)", re.IGNORECASE)

DOCSTRING = "<class docstring>"

# Fields that carry such wording today, each with a short reason. Add to it only on
# purpose; an entry that no longer matches anything fails the gate, so the list cannot
# outlive the field it excuses.
ALLOWLIST: Dict[Tuple[str, str], str] = {
    ("EtfHolding", "localTicker"): (
        "documented on ETF holding rows as the venue-local name of the issuer's symbol"
    ),
}

HOW_TO_FIX = (
    "One value gets one name. Type the name the API docs teach and leave the other "
    "undeclared (callers can still read it with .get()). If a duplicate is really "
    "wanted, add it to ALLOWLIST in this test deliberately, with its reason."
)

Hit = Tuple[str, str, str]  # (class name, field name, offending text)


def _comments(source: str) -> Dict[int, str]:
    found: Dict[int, str] = {}
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            found[tok.start[0]] = tok.string.lstrip("#:").strip()
    return found


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _docstring_field(sentence: str, fields: Set[str]) -> str:
    """The field a docstring sentence talks about: the first one it names."""
    match = PHRASE.search(sentence)
    before = sentence[: match.start()] if match else sentence
    for scope in (before, sentence):
        for name in re.findall(r"``(\w+)``|`(\w+)`", scope):
            candidate = name[0] or name[1]
            if candidate in fields:
                return candidate
    return DOCSTRING


def find_hits(source: str) -> List[Hit]:
    """Every (class, field, text) in ``source`` whose wording names a duplicate."""
    tree = ast.parse(source)
    lines = source.splitlines()
    comments = _comments(source)
    hits: List[Hit] = []
    for cls in (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)):
        body = cls.body
        fields: Set[str] = set()
        for index, stmt in enumerate(body):
            if not (isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)):
                continue
            name = stmt.target.id
            fields.add(name)
            above: List[str] = []
            line = stmt.lineno - 1
            while line in comments and lines[line - 1].lstrip().startswith("#"):
                above.insert(0, comments[line])
                line -= 1
            own = [comments[n] for n in range(stmt.lineno, stmt.end_lineno + 1) if n in comments]
            below: List[str] = []
            following: Optional[ast.stmt] = body[index + 1] if index + 1 < len(body) else None
            if (
                isinstance(following, ast.Expr)
                and isinstance(following.value, ast.Constant)
                and isinstance(following.value.value, str)
            ):
                below.append(following.value.value)
            text = _normalize(" ".join(above + own + below))
            if PHRASE.search(text):
                hits.append((cls.name, name, text))
        doc = ast.get_docstring(cls) or ""
        for sentence in re.split(r"(?<=[.!?])\s+", _normalize(doc)):
            if PHRASE.search(sentence):
                hits.append((cls.name, _docstring_field(sentence, fields), sentence))
    return hits


def _source() -> str:
    return TYPES_PY.read_text(encoding="utf-8")


def test_no_field_is_described_as_a_duplicate():
    offenders = [hit for hit in find_hits(_source()) if hit[:2] not in ALLOWLIST]
    assert not offenders, "%s\n\n%s" % (
        HOW_TO_FIX,
        "\n".join("  %s.%s: %s" % hit for hit in offenders),
    )


def test_every_allowlist_entry_still_matches():
    found = {hit[:2] for hit in find_hits(_source())}
    stale = sorted(set(ALLOWLIST) - found)
    assert not stale, (
        "ALLOWLIST entries that no longer match any wording in types.py; remove them: %s"
        % stale
    )


class TestTheScannerBites:
    """The scan itself, on small sources, so a regex or parser slip cannot pass quietly."""

    SAMPLE = '''
from dataclasses import dataclass
from typing import Optional, TypedDict


@dataclass
class Trailing:
    a: str = ""
    b: Optional[str] = None  # Same value as a.


@dataclass
class Above:
    a: str = ""
    # The short name. An alias of
    # ``a`` kept for older callers.
    b: Optional[str] = None


@dataclass
class Marker:
    a: str = ""
    #: alias for a
    b: Optional[str] = None


@dataclass
class Below:
    a: str = ""
    b: Optional[str] = None
    """Alias of a."""


class Keys(TypedDict, total=False):
    a: str
    b: str  # SAME VALUE AS a


@dataclass
class InDocstring:
    """A row.

    ``b`` is an alias for ``a``, kept for older code.
    """

    a: str = ""
    b: Optional[str] = None


@dataclass
class Clean:
    """Nothing to flag: ``b`` is the value a mentions, and alias is just a word."""

    a: str = ""  # the same values are not compared
    b: Optional[str] = None
'''

    def test_every_attachment_is_caught(self):
        caught = {hit[:2] for hit in find_hits(self.SAMPLE)}
        assert caught == {
            ("Trailing", "b"),
            ("Above", "b"),
            ("Marker", "b"),
            ("Below", "b"),
            ("Keys", "b"),
            ("InDocstring", "b"),
        }

    def test_the_comment_of_one_field_does_not_spill_onto_the_next(self):
        source = (
            "class Row:\n"
            "    a: str = ''  # same value as c\n"
            "    b: str = ''\n"
        )
        assert [hit[:2] for hit in find_hits(source)] == [("Row", "a")]
