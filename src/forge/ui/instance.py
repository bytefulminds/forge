"""Talk to a Forge that is already running, for ``forge --snip``.

The first Forge listens on a local socket (named per user). ``forge --snip``
started from a desktop keyboard shortcut sends "snip" there and exits, so the
running Forge takes the screenshot; without a running Forge it starts one.
"""

from __future__ import annotations

import getpass
import logging
from collections.abc import Callable

from PyQt6.QtCore import QObject
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from forge import APP_ID

log = logging.getLogger(__name__)
TIMEOUT_MS = 800


def server_name() -> str:
    try:
        user = getpass.getuser()
    except (KeyError, OSError):
        user = "user"
    return f"{APP_ID}.{user}"


def send(message: str, name: str | None = None) -> bool:
    """Send ``message`` to the running Forge; False when none is listening."""
    socket = QLocalSocket()
    socket.connectToServer(name or server_name())
    if not socket.waitForConnected(TIMEOUT_MS):
        return False
    socket.write((message + "\n").encode())
    socket.waitForBytesWritten(TIMEOUT_MS)
    socket.disconnectFromServer()
    return True


class InstanceServer(QObject):
    """Receives messages from later ``forge --...`` calls; ``handle(message)``."""

    def __init__(
        self, handle: Callable[[str], None], parent: QObject, name: str | None = None
    ) -> None:
        super().__init__(parent)
        self._handle = handle
        self.name = name or server_name()
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self._accept)
        self.listening = self._listen()

    def _listen(self) -> bool:
        if send("ping", self.name):
            return False  # another Forge already listens; leave it
        QLocalServer.removeServer(self.name)  # a stale socket from a crash
        if not self.server.listen(self.name):
            log.warning("Could not listen on %s: %s", self.name, self.server.errorString())
            return False
        return True

    def _accept(self) -> None:
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            if socket is None:
                continue
            socket.readyRead.connect(lambda s=socket: self._read(s))
            socket.disconnected.connect(socket.deleteLater)

    def _read(self, socket: QLocalSocket) -> None:
        while socket.canReadLine():
            message = bytes(socket.readLine().data()).decode(errors="replace").strip()
            if message and message != "ping":
                self._handle(message)

    def close(self) -> None:
        self.server.close()
