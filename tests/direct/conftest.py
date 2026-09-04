"""Shared helpers for RainGuard direct-mode tests."""

import json
import sys
from datetime import datetime, timedelta, timezone

import pytest

# A fixed "now" for deterministic time travel. Unix 1767225600.
BASE_ISO = "2030-01-01T00:00:00Z"


def to_hex(addr_bytes):
    """Convert address bytes to checksummed hex matching contract output."""
    if hasattr(addr_bytes, "as_hex"):
        return addr_bytes.as_hex
    from genlayer.py.types import Address

    return Address(addr_bytes).as_hex


def addr(addr_bytes):
    """Build an Address object for TreeMap[Address, ...] lookups."""
    from genlayer.py.types import Address

    if isinstance(addr_bytes, Address):
        return addr_bytes
    return Address(addr_bytes)


def set_time(iso_str: str) -> None:
    """Advance the contract's view of block time.

    The direct VM's ``warp()`` does not refresh ``message_raw['datetime']``,
    which is what the contract's ``_now()`` reads, so we mutate it directly.
    """
    import genlayer.gl as gl

    gl.message_raw["datetime"] = iso_str


@pytest.fixture(autouse=True)
def _reset_block_time():
    """Keep block time deterministic across tests.

    ``genlayer.gl`` is imported once per session, so ``message_raw['datetime']``
    leaks between tests. Reset it to a fixed base before and after each test.
    """
    _reset()
    yield
    _reset()


def _reset():
    if "genlayer.gl" in sys.modules:
        gl = sys.modules["genlayer.gl"]
        if getattr(gl, "message_raw", None) is not None:
            gl.message_raw["datetime"] = BASE_ISO


def iso_to_ts(iso_str: str) -> int:
    return int(datetime.fromisoformat(iso_str.replace("Z", "+00:00")).timestamp())


# ---------------------------------------------------------------- RainGuard
# Base block time is 2030-01-01T00:00:00Z (see BASE_ISO above). Policies cover
# the window RG_START_DATE..RG_END_DATE (2030-01-01..2030-01-05), which is
# live at base time, so creation and buying succeed before settlement.
RG_START_DATE = "2030-01-01"
RG_END_DATE = "2030-01-05"
# The daily values the weather mock serves. Sum of precipitation = 1.5 mm;
# max daily temperature = 31.5 C. Both metrics are requested in one fetch.
RG_PRECIP = [0.3, 0.2, 0.5, 0.4, 0.1]
RG_TEMPS = [29.0, 30.1, 31.5, 28.4, 30.2]
# Settlement is eligible the day after RG_END_DATE + 1h buffer
# (2030-01-06T01:00:00Z), which is what SETTLE_ELIGIBLE_ISO must clear.


def mock_weather(vm, precip=None, temps=None):
    """Mock the Open-Meteo archive response the validators fetch."""
    days = [f"2030-01-{d:02d}" for d in range(1, 6)]
    body = json.dumps(
        {
            "daily": {
                "time": days,
                "precipitation_sum": precip if precip is not None else RG_PRECIP,
                "temperature_2m_max": temps if temps is not None else RG_TEMPS,
            }
        }
    )
    vm.mock_web(
        r".*archive-api\.open-meteo\.com.*", {"status": 200, "body": body}
    )


def create_policy(
    contract, vm, insurer, metric="rainfall", lat="-6.2", lon="106.8",
    start=RG_START_DATE, end=RG_END_DATE, threshold="2.0", condition="below",
    premium=100, payout=200,
):
    """Insurer creates a policy with the exact payout; returns its int id."""
    vm.sender = insurer
    vm.value = payout
    pid = int(contract.create_policy(
        metric, lat, lon, start, end, threshold, condition, premium, payout,
    ))
    vm.value = 0
    return pid


def funded_policy(contract, vm, insurer, buyer, **kwargs):
    """Create a policy and have the buyer purchase it; returns its int id."""
    premium = kwargs.get("premium", 100)
    pid = create_policy(contract, vm, insurer, **kwargs)
    vm.sender = buyer
    vm.value = premium
    contract.buy_policy(pid)
    vm.value = 0
    return pid
