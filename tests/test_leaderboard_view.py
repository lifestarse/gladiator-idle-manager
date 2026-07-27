# Build: 2
"""Poll/error paths of game.leaderboard.leaderviewmixin.

Desktop-only tests: no jnius, no real Kivy Clock. Clock is monkeypatched
with a manually-ticked fake; Play Games task/client are fakes.
"""
import pytest

import game.leaderboard.leaderviewmixin as lvm

# _check_task gives up once its tick counter exceeds 100 → tick 101 fires it.
TIMEOUT_TICKS = 101


class FakeClock:
    """Minimal Clock stand-in: records (un)scheduling, ticked manually."""

    def __init__(self):
        self.intervals = []    # active interval callbacks
        self.unscheduled = []  # every unschedule() argument, in order

    def schedule_once(self, cb, timeout=0):
        cb(0)

    def schedule_interval(self, cb, interval):
        self.intervals.append(cb)

    def unschedule(self, cb):
        self.unscheduled.append(cb)
        self.intervals = [c for c in self.intervals if c is not cb]

    def tick(self, n=1):
        """Fire every active interval callback n times."""
        for _ in range(n):
            if not self.intervals:
                return
            for cb in list(self.intervals):
                cb(0.1)


class FakeTask:
    """Play Games Task fake."""

    def __init__(self, complete=False, successful=True, result="intent",
                 exception=None, complete_error=None):
        self._complete = complete
        self._successful = successful
        self._result = result
        self._exception = exception
        self._complete_error = complete_error

    def isComplete(self):
        if self._complete_error is not None:
            raise self._complete_error
        return self._complete

    def isSuccessful(self):
        return self._successful

    def getResult(self):
        return self._result

    def getException(self):
        return self._exception


class FakeClient:
    def __init__(self, task, intent_error=None):
        self._task = task
        self._intent_error = intent_error
        self.requested_ids = []

    def getLeaderboardIntent(self, leaderboard_id):
        self.requested_ids.append(leaderboard_id)
        if self._intent_error is not None:
            raise self._intent_error
        return self._task

    def getAllLeaderboardsIntent(self):
        self.requested_ids.append(None)
        if self._intent_error is not None:
            raise self._intent_error
        return self._task


class Host(lvm._LeaderViewMixin):
    """Bare mixin host: no Java, records launched intents."""

    def __init__(self, client=None, initialized=True):
        self._initialized = initialized
        self._client = client
        self.status = ""
        self.launched = []

    def _get_client(self):
        return self._client

    def _launch_intent(self, intent):
        self.launched.append(intent)
        self.status = "Showing leaderboard"


class FailureSpy:
    def __init__(self):
        self.calls = []

    def __call__(self, err):
        self.calls.append(err)


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(lvm, "Clock", fake)
    return fake


def test_timeout_sets_status_calls_on_failure_and_unschedules(clock):
    host = Host()
    spy = FailureSpy()
    host._lbview_poll_task(FakeTask(complete=False), spy)
    assert len(clock.intervals) == 1
    cb = clock.intervals[0]

    clock.tick(TIMEOUT_TICKS)

    assert spy.calls == ["Timeout"]
    assert host.status == "Error: Timeout"
    assert cb in clock.unscheduled
    assert clock.intervals == []


def test_timeout_straggler_tick_does_not_refire(clock):
    # A tick already queued by the real Clock can still fire after
    # unschedule; on_failure must stay exactly-once.
    host = Host()
    spy = FailureSpy()
    host._lbview_poll_task(FakeTask(complete=False), spy)
    cb = clock.intervals[0]
    clock.tick(TIMEOUT_TICKS)
    assert spy.calls == ["Timeout"]

    cb(0.1)  # straggler tick after unschedule

    assert spy.calls == ["Timeout"]


def test_is_complete_raises_sets_status_calls_on_failure_and_unschedules(clock):
    host = Host()
    spy = FailureSpy()
    host._lbview_poll_task(FakeTask(complete_error=RuntimeError("boom")), spy)
    cb = clock.intervals[0]

    clock.tick()

    assert spy.calls == ["boom"]
    assert host.status == "Error: boom"
    assert cb in clock.unscheduled
    assert clock.intervals == []


def test_timeout_without_callback_still_sets_status(clock):
    host = Host()
    host._lbview_poll_task(FakeTask(complete=False), None)
    clock.tick(TIMEOUT_TICKS)
    assert host.status == "Error: Timeout"
    assert clock.intervals == []


def test_poll_error_without_callback_still_sets_status(clock):
    host = Host()
    host._lbview_poll_task(FakeTask(complete_error=RuntimeError("boom")), None)
    clock.tick()
    assert host.status == "Error: boom"
    assert clock.intervals == []


def test_pending_task_keeps_polling(clock):
    host = Host()
    spy = FailureSpy()
    host._lbview_poll_task(FakeTask(complete=False), spy)

    clock.tick(TIMEOUT_TICKS - 1)  # one short of the limit

    assert clock.intervals != []
    assert spy.calls == []
    assert host.status == ""


def test_success_launches_intent_without_failure(clock):
    host = Host()
    spy = FailureSpy()
    task = FakeTask(complete=True, successful=True, result="the-intent")
    host._lbview_poll_task(task, spy)
    cb = clock.intervals[0]

    clock.tick()

    assert host.launched == ["the-intent"]
    assert spy.calls == []
    assert cb in clock.unscheduled


def test_task_failure_reports_exception_once(clock):
    host = Host()
    spy = FailureSpy()
    task = FakeTask(complete=True, successful=False, exception="java.lang.Boom")
    host._lbview_poll_task(task, spy)

    clock.tick()

    assert spy.calls == ["java.lang.Boom"]
    assert host.status == "Error: java.lang.Boom"


def test_task_failure_without_exception_uses_unknown_error(clock):
    host = Host()
    spy = FailureSpy()
    task = FakeTask(complete=True, successful=False, exception=None)
    host._lbview_poll_task(task, spy)

    clock.tick()

    assert spy.calls == ["Unknown error"]
    assert host.status == "Error: Unknown error"


def test_intent_request_raises_sets_status_and_reports_once(clock):
    client = FakeClient(FakeTask(), intent_error=RuntimeError("boom"))
    host = Host(client=client)
    spy = FailureSpy()

    host.show_leaderboard("LB_ID", on_failure=spy)

    assert spy.calls == ["boom"]
    assert host.status == "Error: boom"
    assert clock.intervals == []  # poll never started


def test_intent_request_raises_without_callback_still_sets_status(clock):
    client = FakeClient(FakeTask(), intent_error=RuntimeError("boom"))
    host = Host(client=client)

    host.show_leaderboard("LB_ID", on_failure=None)

    assert host.status == "Error: boom"
    assert clock.intervals == []


def test_show_leaderboard_full_flow_via_fake_client(clock):
    task = FakeTask(complete=True, successful=True, result="intent-42")
    client = FakeClient(task)
    host = Host(client=client)
    spy = FailureSpy()

    host.show_leaderboard("LB_ID", on_failure=spy)  # schedule_once fires inline
    clock.tick()

    assert client.requested_ids == ["LB_ID"]
    assert host.launched == ["intent-42"]
    assert spy.calls == []


def test_show_all_leaderboards_requests_all(clock):
    task = FakeTask(complete=True, successful=True)
    client = FakeClient(task)
    host = Host(client=client)

    host.show_all_leaderboards()
    clock.tick()

    assert client.requested_ids == [None]
    assert host.launched == ["intent"]


def test_show_leaderboard_not_signed_in(clock):
    host = Host(initialized=False)
    spy = FailureSpy()

    host.show_leaderboard(on_failure=spy)

    assert spy.calls == ["Not signed in"]


def test_no_client_reports_not_connected(clock):
    host = Host(client=None)
    spy = FailureSpy()

    host.show_leaderboard(on_failure=spy)

    assert spy.calls == ["Not connected"]
    assert host.status == "Not connected"
