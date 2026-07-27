# Build: 3
"""HTTPS fetch (JSON and raw bytes), hardened against a hostile upstream.

Extracted from game/scripting/online_library.py, which was the first consumer
and still uses it — there must be exactly one place that knows how to talk
HTTPS on Android, because the certifi wiring below is easy to get wrong and
fails only on device, never in tests.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import logging
import ssl
import urllib.error
import urllib.request

_log = logging.getLogger(__name__)

# Short: a broken DNS must not hold a worker thread for a minute.
DEFAULT_TIMEOUT_S = 5.0
USER_AGENT = "gladiator-idle-manager/1.0"


def ssl_context() -> ssl.SSLContext:
    """An SSLContext backed by certifi's CA bundle.

    On python-for-android the stdlib ssl module does not pick up the system
    root store, so a default-context HTTPS request dies with::

        ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED]
        unable to get local issuer certificate

    even though certifi is in buildozer requirements — it ships but is never
    wired in. Building the context explicitly from certifi.where() works on
    every platform; on desktop it resolves to the same file stdlib would have
    found anyway.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception as exc:  # noqa: BLE001 - any certifi failure falls back
        _log.warning("[remote] certifi unavailable, using default SSL context: %s", exc)
        return ssl.create_default_context()


CHUNK_BYTES = 16 * 1024


def _read_capped(url, timeout, max_bytes, on_bytes):
    """The shared streaming GET: returns the raw body bytes, or None.

    max_bytes caps the body so a hijacked or misconfigured upstream cannot
    balloon device memory by streaming forever. The cap is enforced DURING the
    read, not after: reading an unbounded body and then measuring it is the
    same as not having a cap.

    on_bytes(received, total) is called as the body arrives so a download can
    show a real progress bar. total is None when the server sends no
    Content-Length, and the caller should fall back to an indeterminate
    indicator rather than inventing a denominator.

    Raises what urlopen raises — the public wrappers own the error policy.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout,
                                context=ssl_context()) as response:
        total = response.headers.get("Content-Length")
        try:
            total = int(total) if total is not None else None
        except (TypeError, ValueError):
            total = None
        if total is not None and total > max_bytes:
            _log.warning("[remote] %s declares %d bytes, over the %d cap",
                         url, total, max_bytes)
            return None
        chunks, received = [], 0
        while True:
            chunk = response.read(CHUNK_BYTES)
            if not chunk:
                break
            received += len(chunk)
            if received > max_bytes:
                _log.warning("[remote] %s exceeded %d bytes — rejected",
                             url, max_bytes)
                return None
            chunks.append(chunk)
            if on_bytes:
                try:
                    on_bytes(received, total)
                except Exception:  # noqa: BLE001 - a UI callback must not abort the fetch
                    pass
    return b"".join(chunks)


def fetch_json(url, timeout=DEFAULT_TIMEOUT_S, max_bytes=1024 * 1024, on_bytes=None):
    """GET a JSON document. Returns the parsed value, or None on any failure.

    Never raises. Every caller runs on a worker thread, so a failure here must
    be a quiet no-op — the game already has bundled content and is not waiting
    on this.
    """
    try:
        body = _read_capped(url, timeout, max_bytes, on_bytes)
        if body is None:
            return None
        return json.loads(body.decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError,
            http.client.HTTPException, OSError, ValueError, RecursionError) as exc:
        # RecursionError: a size cap alone does not stop {"a":{"a":{... x50k}}}.
        # HTTPException: a body cut short mid-read raises IncompleteRead, which
        # urllib does NOT wrap in URLError — it would escape "never raises" and
        # kill the caller's worker thread, leaving the picker row spinning.
        _log.warning("[remote] fetch failed for %s (%s): %s",
                     url, type(exc).__name__, exc)
        return None


def fetch_bytes(url, timeout=DEFAULT_TIMEOUT_S, max_bytes=1024 * 1024,
                on_bytes=None, sha256=None):
    """GET a binary file (a font). Returns the body bytes, or None on failure.

    Never raises, same policy as fetch_json. When ``sha256`` is given the body
    must hash to exactly that hex digest — a binary that gets handed to a
    native renderer (freetype) deserves an integrity check, not just a size
    cap. Mismatch means a truncated or tampered transfer; the caller keeps
    whatever it already has.
    """
    try:
        body = _read_capped(url, timeout, max_bytes, on_bytes)
    except (urllib.error.URLError, urllib.error.HTTPError,
            http.client.HTTPException, OSError, ValueError) as exc:
        _log.warning("[remote] fetch failed for %s (%s): %s",
                     url, type(exc).__name__, exc)
        return None
    if body is None:
        return None
    if sha256 is not None:
        digest = hashlib.sha256(body).hexdigest()
        if digest != sha256.lower():
            _log.warning("[remote] %s sha256 mismatch: got %s, manifest says %s",
                         url, digest, sha256)
            return None
    return body
