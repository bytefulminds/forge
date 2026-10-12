"""Run blocking work on a background thread and get the result on the UI thread."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

log = logging.getLogger(__name__)


class _Signals(QObject):
    done = pyqtSignal(object)
    failed = pyqtSignal(object)


class _Job(QRunnable):
    def __init__(self, fn: Callable[[], Any], signals: _Signals) -> None:
        super().__init__()
        self._fn = fn
        self._signals = signals

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:
            log.debug("Background task failed", exc_info=True)
            self._signals.failed.emit(exc)
        else:
            self._signals.done.emit(result)


_alive: set[_Signals] = set()


def run_in_background(
    fn: Callable[[], Any],
    on_done: Callable[[Any], None],
    on_error: Callable[[Exception], None],
) -> None:
    """Run ``fn`` on the global thread pool; callbacks run on the UI thread."""
    signals = _Signals()
    _alive.add(signals)  # keep the QObject alive until a callback has run

    def finish(callback: Callable[[Any], None], value: Any) -> None:
        _alive.discard(signals)
        callback(value)

    signals.done.connect(lambda value: finish(on_done, value))
    signals.failed.connect(lambda exc: finish(on_error, exc))
    QThreadPool.globalInstance().start(_Job(fn, signals))  # type: ignore[union-attr]
