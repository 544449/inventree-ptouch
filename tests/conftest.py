import pytest

REAL_STATUS = bytes.fromhex(
    "80204230" "7f302200" "00000c01" "00000000" "00000000" "00000000" "01080000" "00000000")


def with_bytes(**changes):
    b = bytearray(REAL_STATUS)
    for idx, val in changes.items():
        b[int(idx[1:])] = val
    return bytes(b)


@pytest.fixture
def real_status():
    return REAL_STATUS
