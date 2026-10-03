"""Hard time limit for calls that may hang (a stuck browser, DNS without a network)."""
import threading
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class CallTimeout(TimeoutError):
    """The call did not finish within the limit."""


def call_with_timeout(fn: Callable[[], T], timeout_sec: float) -> T:
    """Run `fn` in a daemon thread and wait at most `timeout_sec` for it.

    Raises `CallTimeout` when the limit passes; whatever `fn` raises is re-raised here.
    A timed-out call cannot be killed: it is left to finish on its own and its result is dropped.
    """
    outcome: list = []

    def run() -> None:
        try:
            outcome.append((True, fn()))
        except BaseException as e:  # handed over to the caller's thread
            outcome.append((False, e))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout_sec)
    if not outcome:
        raise CallTimeout(f"no answer within {timeout_sec:g} s")
    ok, value = outcome[0]
    if ok:
        return value
    raise value
