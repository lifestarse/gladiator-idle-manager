# Build: 1
"""game/version.py and buildozer.spec must agree.

The version exists twice because buildozer.spec drives the release but is not
packaged into the APK, while remote content patches need to gate on a version
at runtime. Two copies of a number is a hazard; this test is the mechanism that
makes it a safe one.
"""
import re
from pathlib import Path

from game.version import APP_VERSION, at_least, at_most, version_tuple

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "buildozer.spec"


def _spec_version():
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\s*version\s*=\s*(\S+)\s*$", line)
        if match:
            return match.group(1)
    return None


def test_spec_declares_a_version():
    assert _spec_version(), "buildozer.spec has no 'version = ' line"


def test_version_matches_buildozer_spec():
    spec = _spec_version()
    assert spec == APP_VERSION, (
        f"buildozer.spec says {spec!r} but game/version.py says {APP_VERSION!r}. "
        f"Bump both — remote content patches gate on the runtime value."
    )


def test_version_tuple_parses_dotted_numbers():
    assert version_tuple("1.9.44") == (1, 9, 44)
    assert version_tuple("2.0") == (2, 0)


def test_version_tuple_survives_malformed_input():
    """A bad version in a remote manifest degrades, it does not raise."""
    assert version_tuple("") == ()
    assert version_tuple("not-a-version") == ()
    assert version_tuple("1.9.44-beta") == (1, 9, 44)
    assert version_tuple("1.x.3") == (1,)


def test_bounds_compare_against_this_build():
    assert at_least("0.0.1")
    assert not at_least("99.0.0")
    assert at_most("99.0.0")
    assert not at_most("0.0.1")
