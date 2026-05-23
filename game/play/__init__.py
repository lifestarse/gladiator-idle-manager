# Build: 1
"""Google Play Services wrappers — In-App Review for now, room for more.

Anything that touches pyjnius / Java classes lives in this package so
the rest of the engine stays platform-agnostic. Every public entry
point in here MUST silently no-op on non-Android (desktop / pytest)
— callers should not have to guard their calls with platform checks.
"""
from .in_app_review import maybe_show_review  # noqa: F401

__all__ = ["maybe_show_review"]
