# Build: 4
"""The app version, readable at runtime.

buildozer.spec stays the source of truth for releases — the documented workflow
is to bump it there before a build — but its value is not reachable from inside
the APK (.spec is not in source.include_exts). Remote content patches need a
version to gate on: a balance patch written for 1.9.45 must not land on a 1.9.44
client whose formula differs.

So the number lives in both places and tests/test_version_sync.py fails the
build if they ever disagree. Bump both, or the test tells you which one you
forgot.
"""

APP_VERSION = "1.9.47"


def version_tuple(text=None):
    """Parse a dotted version into a comparable tuple of ints.

    Non-numeric trailing parts ("1.9.44-beta") are dropped rather than raising:
    a malformed version in a remote manifest must degrade to "does not apply"
    rather than crash the fetch thread.

    Only ``None`` means "this build". An empty or unparseable string yields the
    empty tuple, which compares below every real version — so a manifest with a
    blank ``min_app`` is treated as garbage, not as "applies everywhere".
    """
    parts = []
    for chunk in str(APP_VERSION if text is None else text).split("."):
        digits = ""
        for char in chunk:
            if not char.isdigit():
                break
            digits += char
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def at_least(minimum):
    """True if this build is >= the given dotted version string."""
    return version_tuple() >= version_tuple(minimum)


def at_most(maximum):
    """True if this build is <= the given dotted version string."""
    return version_tuple() <= version_tuple(maximum)
