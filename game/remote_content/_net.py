# Build: 1
"""Is there a usable network right now?

Checked before every fetch so an offline launch skips cleanly instead of
burning a five-second DNS timeout on a worker thread and reporting a failure
the player cannot act on. ACCESS_NETWORK_STATE is already in buildozer.spec.

Off Android there is no cheap authoritative answer, so the honest thing is to
say "probably" and let the request itself decide — the fetch path already
treats every failure as a no-op.
"""
from __future__ import annotations

import logging

_log = logging.getLogger(__name__)


def is_online():
    """True when a fetch is worth attempting.

    Never raises: any failure to determine connectivity is reported as "yes",
    because a wrong "no" silently disables updates forever while a wrong "yes"
    costs one timed-out request.
    """
    try:
        from kivy.utils import platform
    except Exception:  # noqa: BLE001 - kivy absent (tests, tooling)
        return True
    if platform != "android":
        return True
    try:
        from jnius import autoclass, cast
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")
        activity = PythonActivity.mActivity
        service = activity.getSystemService(Context.CONNECTIVITY_SERVICE)
        manager = cast("android.net.ConnectivityManager", service)

        # getActiveNetworkInfo is deprecated since API 29 but still present and
        # is the only one-call answer that works across every level p4a builds
        # for. NetworkCapabilities is tried first where available.
        try:
            network = manager.getActiveNetwork()
            if network is None:
                return False
            caps = manager.getNetworkCapabilities(network)
            if caps is None:
                return False
            NetworkCapabilities = autoclass("android.net.NetworkCapabilities")
            return bool(caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET))
        except Exception:  # noqa: BLE001 - older API level
            info = manager.getActiveNetworkInfo()
            return bool(info is not None and info.isConnected())
    except Exception as exc:  # noqa: BLE001 - jnius missing or API change
        _log.info("[remote] connectivity check unavailable (%s) — assuming online", exc)
        return True
