import socket
import time
from typing import Callable

from .errors import PrinterError, PrinterUnreachable
from .protocol import INIT, INVALIDATE, STATUS_REQUEST, STATUS_SIZE, Status

SYNC = b"\x80\x20"
ST_REPLY, ST_COMPLETED, ST_ERROR = 0x00, 0x01, 0x02
POLL = 0.5


def _rfcomm_socket() -> socket.socket:
    return socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)


class RfcommLink:
    def __init__(self, mac: str, channel: int = 2, timeout: float = 10.0,
                 socket_factory: Callable[[], socket.socket] | None = None):
        self.mac = mac
        self.channel = channel
        self.timeout = timeout
        self._factory = socket_factory or _rfcomm_socket
        self._sock = None
        self._buf = b""

    def connect(self) -> None:
        sock = self._factory()
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.mac, self.channel))
        except OSError as e:
            sock.close()
            raise PrinterUnreachable(
                f"printer {self.mac} not reachable over Bluetooth "
                f"(switched off, asleep or out of range?): {e}") from e
        self._sock = sock

    def send(self, data: bytes) -> None:
        try:
            self._sock.sendall(data)
        except OSError as e:
            raise PrinterError(f"sending to printer failed: {e}") from e

    def read_status(self, timeout: float) -> Status:
        deadline = time.monotonic() + timeout
        while True:
            status = self._pop_status()
            if status:
                return status
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PrinterError("no answer from printer")
            self._sock.settimeout(min(remaining, POLL))
            try:
                chunk = self._sock.recv(256)
            except (socket.timeout, TimeoutError):
                continue
            except OSError as e:
                raise PrinterError(f"reading from printer failed: {e}") from e
            if not chunk:
                raise PrinterError("printer closed the connection")
            self._buf += chunk

    def _pop_status(self) -> Status | None:
        while True:
            i = self._buf.find(SYNC)
            if i < 0:
                self._buf = self._buf[-1:]
                return None
            self._buf = self._buf[i:]
            if len(self._buf) < STATUS_SIZE:
                return None
            try:
                status = Status.parse(self._buf[:STATUS_SIZE])
            except ValueError:
                self._buf = self._buf[1:]
                continue
            self._buf = self._buf[STATUS_SIZE:]
            return status

    def close(self) -> None:
        if self._sock:
            self._sock.close()
            self._sock = None

    def __enter__(self) -> "RfcommLink":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def query_status(link: RfcommLink, timeout: float = 10.0) -> Status:
    link.send(INVALIDATE + INIT + STATUS_REQUEST)
    deadline = time.monotonic() + timeout
    while True:
        status = link.read_status(max(deadline - time.monotonic(), 0))
        if status.status_type == ST_REPLY:
            return status


def print_pages(link: RfcommLink, pages: list[bytes], page_timeout: float = 60.0) -> None:
    for page in pages:
        link.send(page)
        deadline = time.monotonic() + page_timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PrinterError("printer did not report the label as printed")
            try:
                status = link.read_status(remaining)
            except PrinterError as e:
                raise PrinterError(f"printer did not report the label as printed: {e}") from e
            if status.status_type == ST_ERROR:
                raise PrinterError("; ".join(status.problems()) or "printer reported an error")
            if status.status_type == ST_COMPLETED:
                break
