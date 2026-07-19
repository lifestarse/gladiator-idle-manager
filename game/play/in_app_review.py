# Build: 1
"""Google Play In-App Review trigger.

Wraps the Play Core Review API (com.google.android.play:review) through
pyjnius. The public surface is one call: ``maybe_show_review()`` —
fire-and-forget, never raises, no return.

Why a wrapper at all (vs calling pyjnius from engine code):
  - Engine stays portable: pytest + desktop runs don't import jnius.
  - Java classloading / listener interfaces are finicky; isolating them
    here means a Play Core version bump only touches one file.
  - Google rate-limits the prompt internally (max ~once per several
    months per user), so this function is safe to call from any
    "interesting event" hook without us having to track our own quota.

API flow (per Google docs):
    ReviewManager m = ReviewManagerFactory.create(activity);
    Task<ReviewInfo> req = m.requestReviewFlow();
    req.addOnCompleteListener(task -> {
        if (task.isSuccessful()) {
            ReviewInfo info = task.getResult();
            m.launchReviewFlow(activity, info);  // returns Task<Void>
        }
    });

Non-success outcomes (offline, quota exceeded, account not signed in)
are silently swallowed — the official guidance is to never tell the
user they can't review, just don't show the prompt.
"""
from __future__ import annotations
import logging

_log = logging.getLogger(__name__)


def maybe_show_review() -> None:
    """Request and (if approved by Play) launch the In-App Review flow.

    Safe to call any time on any platform. Every failure mode (no jnius,
    no Activity, no Play Services, quota exhausted, network down)
    returns silently after a single log line at WARNING (or below).
    """
    try:
        from jnius import autoclass, PythonJavaClass, java_method
    except ImportError:
        _log.info("[review] jnius unavailable — skipping (desktop / test run)")
        return

    try:
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        if activity is None:
            _log.warning("[review] PythonActivity.mActivity is None")
            return

        ReviewManagerFactory = autoclass(
            "com.google.android.play.core.review.ReviewManagerFactory")
        manager = ReviewManagerFactory.create(activity)

        # ReviewManager.requestReviewFlow() returns Task<ReviewInfo>. The
        # Play Core Review library bundles its own Task type rooted at
        # com.google.android.play.core.tasks.Task — NOT the GMS Tasks
        # API. That's the namespace we have to point our listener at.
        class _OnRequestComplete(PythonJavaClass):
            __javainterfaces__ = [
                "com/google/android/play/core/tasks/OnCompleteListener"]
            __javacontext__ = "app"

            @java_method("(Lcom/google/android/play/core/tasks/Task;)V")
            def onComplete(self, task):
                try:
                    if not task.isSuccessful():
                        # Common: quota exceeded, no signed-in account,
                        # not installed via Play. Nothing actionable.
                        _log.info("[review] requestReviewFlow not successful")
                        return
                    review_info = task.getResult()
                    # launchReviewFlow returns its own Task<Void> — we
                    # don't need to wait for completion. Play overlays
                    # the bottom-sheet on top of our Activity and
                    # closes itself.
                    manager.launchReviewFlow(activity, review_info)
                    _log.info("[review] launchReviewFlow dispatched")
                except Exception as exc:
                    _log.warning(
                        "[review] onComplete handler failed: %s", exc)

        request_task = manager.requestReviewFlow()
        request_task.addOnCompleteListener(_OnRequestComplete())
        _log.info("[review] requestReviewFlow scheduled")
    except Exception as exc:
        # autoclass() can throw if Play Core isn't bundled in this AAB
        # (e.g. forgot the gradle dependency). Whole pipeline fails
        # closed — game keeps running, just no prompt.
        _log.warning("[review] In-App Review pipeline unavailable: %s", exc)
