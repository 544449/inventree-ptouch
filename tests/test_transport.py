import socket

import pytest

from conftest import REAL_STATUS, with_bytes
from inventree_ptouch.transport import (
    PrinterError, PrinterUnreachable, RfcommLink, print_pages, query_status)


class FakeSocket:
    def __init__(self, chunks=(), connect_exc=None):
        self.chunks = list(chunks)
        self.connect_exc = connect_exc
        self.sends = []
        self.closed = False
        self.addr = None

    def settimeout(self, t):
        pass

    def connect(self, addr):
        self.addr = addr
        if self.connect_exc:
            raise self.connect_exc

    def sendall(self, data):
        self.sends.append(bytes(data))

    def recv(self, n):
        if not self.chunks:
            raise socket.timeout()
        return self.chunks.pop(0)

    def close(self):
        self.closed = True

    @property
    def sent(self):
        return b"".join(self.sends)


def link_with(sock, **kw):
    return RfcommLink("00:11:22:33:44:55", socket_factory=lambda: sock, **kw)


def test_connect_uses_mac_and_channel():
    sock = FakeSocket()
    with link_with(sock, channel=2):
        pass
    assert sock.addr == ("00:11:22:33:44:55", 2) and sock.closed


def test_connect_timeout_raises_unreachable():
    with pytest.raises(PrinterUnreachable):
        link_with(FakeSocket(connect_exc=TimeoutError())).connect()


def test_connect_oserror_raises_unreachable():
    with pytest.raises(PrinterUnreachable, match="00:11:22:33:44:55"):
        link_with(FakeSocket(connect_exc=OSError(112, "Host is down"))).connect()


def test_query_status_sends_init_and_parses():
    sock = FakeSocket(chunks=[REAL_STATUS[:10], REAL_STATUS[10:]])
    with link_with(sock) as link:
        assert query_status(link).media_width == 12
    assert sock.sent == b"\x00" * 200 + b"\x1b@\x1biS"


def test_query_status_skips_unsolicited_packets():
    sock = FakeSocket(chunks=[with_bytes(b18=0x06), REAL_STATUS])
    with link_with(sock) as link:
        assert query_status(link).status_type == 0


def test_read_status_resyncs_on_garbage():
    sock = FakeSocket(chunks=[b"\x00\x00\x80" + REAL_STATUS])
    with link_with(sock) as link:
        assert link.read_status(1).model == 0x7F


def test_read_status_timeout_raises():
    with link_with(FakeSocket()) as link:
        with pytest.raises(PrinterError):
            link.read_status(0.2)


def test_print_pages_waits_for_completion_each_page():
    sock = FakeSocket(chunks=[with_bytes(b18=0x06), with_bytes(b18=0x01),
                              with_bytes(b18=0x06), with_bytes(b18=0x01)])
    with link_with(sock) as link:
        print_pages(link, [b"P1", b"P2"])
    assert sock.sends == [b"P1", b"P2"]


def test_second_page_not_sent_before_first_completes():
    sock = FakeSocket(chunks=[with_bytes(b18=0x06)])
    with link_with(sock) as link:
        with pytest.raises(PrinterError):
            print_pages(link, [b"P1", b"P2"], page_timeout=0.2)
    assert sock.sends == [b"P1"]


def test_error_status_during_print_raises():
    sock = FakeSocket(chunks=[with_bytes(b18=0x02, b9=0x10)])
    with link_with(sock) as link:
        with pytest.raises(PrinterError, match="(?i)cover open"):
            print_pages(link, [b"P1"])


def test_no_completion_times_out():
    with link_with(FakeSocket()) as link:
        with pytest.raises(PrinterError):
            print_pages(link, [b"P1"], page_timeout=0.2)


def test_closed_connection_raises():
    sock = FakeSocket(chunks=[b""])
    with link_with(sock) as link:
        with pytest.raises(PrinterError):
            link.read_status(1)
