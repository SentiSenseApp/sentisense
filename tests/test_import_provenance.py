"""Guards that the suite runs against this working tree, not an installed copy.

If the package is also installed in the ambient environment, ``import sentisense``
can resolve to site-packages instead of ``src/``. Every other test then exercises
the *released* code: the suite reports all green while the changes under review are
never executed at all. Nothing about that failure is visible from the output, so it
gets its own explicit check rather than being left to chance.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import sentisense

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_PACKAGE_DIR = REPO_ROOT / "src" / "sentisense"

_HOW_TO_FIX = """
How to fix, cheapest first:
  1. Run pytest from the repository root, so the `pythonpath = ["src"]` setting in
     pyproject.toml applies. Running it from elsewhere can pick a different rootdir
     and silently drop that setting.
  2. Force it for one run:  PYTHONPATH=src python3 -m pytest tests/
  3. Remove the shadowing copy:  python3 -m pip uninstall sentisense
"""


def _imported_package_dir() -> Path:
    return Path(sentisense.__file__).resolve().parent


def _version_on_disk() -> str:
    """Read the version out of the working tree WITHOUT importing the package.

    Importing ``sentisense.__about__`` would load it from whichever copy won the
    import, which is the very thing under test. Parsing the file on disk keeps this
    an independent reference point.
    """
    about_path = EXPECTED_PACKAGE_DIR / "__about__.py"
    match = re.search(
        r"""__version__\s*=\s*["']([^"']+)["']""",
        about_path.read_text(encoding="utf-8"),
    )
    assert match is not None, f"no __version__ assignment found in {about_path}"
    return match.group(1)


def test_package_is_imported_from_this_working_tree() -> None:
    """`import sentisense` must resolve to src/, not to an installed copy."""
    imported_dir = _imported_package_dir()
    if imported_dir == EXPECTED_PACKAGE_DIR:
        return

    raise AssertionError(
        "This test run is NOT testing this working tree.\n\n"
        f"  `import sentisense` resolved to: {imported_dir}\n"
        f"  ...but it should have resolved to: {EXPECTED_PACKAGE_DIR}\n\n"
        "Everything else in this suite just exercised that other copy. A green run "
        "therefore proves nothing about the code you are editing: any change to an "
        "existing method would pass while the real implementation went untouched.\n"
        f"{_HOW_TO_FIX}\n"
        "First few sys.path entries, for diagnosis:\n"
        + "\n".join(f"  [{i}] {entry}" for i, entry in enumerate(sys.path[:6]))
    )


def test_package_version_matches_this_working_tree() -> None:
    """The imported __version__ must match src/sentisense/__about__.py on disk."""
    imported_version = sentisense.__version__
    disk_version = _version_on_disk()
    if imported_version == disk_version:
        return

    raise AssertionError(
        "The imported package reports a different version than this working tree.\n\n"
        f"  sentisense.__version__ ......... {imported_version!r}\n"
        f"  src/sentisense/__about__.py .... {disk_version!r}\n"
        f"  imported from ................. {_imported_package_dir()}\n\n"
        "Almost always this means an installed copy shadowed the checkout, so the "
        "suite is validating released code instead of the code under review. If the "
        "import path above IS this repository, then __init__.py has drifted from "
        "__about__.py and should read the version from it rather than restating it.\n"
        f"{_HOW_TO_FIX}"
    )
