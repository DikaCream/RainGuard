"""Integration tests for RainGuard — require GenLayer Studio running.

Run with: gltest --network studionet tests/integration/test_rain_guard.py -v -s

These exercise the real consensus pipeline: an insurer funds a policy's payout
escrow, a second wallet buys the coverage by paying the premium, and the
contract's views (including Address-typed personal lists) reflect the state
on-chain. Settlement itself is time-gated — it only runs after the coverage
window has fully ended plus an archive buffer, so a freshly created policy can
not be settled mid-window; that gate is asserted here. The deterministic
settlement math (strict_eq over the Open-Meteo archive response) is covered
exhaustively by the fast direct-mode tests, and the live demo policies settle
with real validator consensus once their windows end.
"""

import datetime

import pytest
from genlayer_py.types import CalldataAddress
from gltest import get_accounts, get_contract_factory
from gltest.assertions import tx_execution_succeeded

# A stable real city: Jakarta. The window starts today so the policy is
# creatable and buyable at any run time, and ends soon enough to be
# settle-eligible shortly after.
LAT = "-6.2"
LON = "106.8"
PREMIUM = 100  # wei amounts; StudioNet GEN has 18 decimals
PAYOUT = 200
THRESHOLD = "100.0"  # mm — a drought trigger unlikely to hit mid-window
MAX_WAIT_SECONDS = 120
POLL_SECONDS = 5


def _today_str() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def _in_days(days: int) -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=days)
    ).strftime("%Y-%m-%d")


def _deploy(account):
    factory = get_contract_factory("RainGuard")
    contract = factory.deploy(account=account)

    stats = contract.get_stats(args=[]).call()
    assert stats["total_policies"] == 0
    assert stats["escrow_locked"] == 0
    return contract


@pytest.mark.integration
def test_create_buy_reach_consensus_and_settlement_is_gated():
    accounts = get_accounts()
    insurer, buyer = accounts[0], accounts[1]
    contract = _deploy(account=insurer)

    # Insurer funds a rainfall policy covering today..tomorrow.
    receipt = contract.create_policy(
        args=[
            "rainfall", LAT, LON, _today_str(), _in_days(1),
            THRESHOLD, "below", PREMIUM, PAYOUT,
        ],
    ).transact(value=PAYOUT, wait_interval=10000, wait_retries=15)
    assert tx_execution_succeeded(receipt)

    policy = contract.get_policy(args=[1]).call()
    assert policy is not None
    assert policy["status"] == "OPEN"
    assert policy["insurer"].lower() == insurer.address.lower()
    assert policy["metric"] == "rainfall"
    assert policy["payout"] == PAYOUT
    stats = contract.get_stats(args=[]).call()
    assert stats["total_policies"] == 1
    assert stats["open"] == 1
    assert stats["escrow_locked"] == PAYOUT

    # A second wallet buys the coverage by paying the premium.
    contract = contract.connect(buyer)
    receipt = contract.buy_policy(
        args=[1],
    ).transact(value=PREMIUM, wait_interval=10000, wait_retries=15)
    assert tx_execution_succeeded(receipt)

    policy = contract.get_policy(args=[1]).call()
    assert policy["status"] == "ACTIVE"
    assert policy["buyer"].lower() == buyer.address.lower()
    stats = contract.get_stats(args=[]).call()
    assert stats["active"] == 1
    assert stats["open"] == 0
    assert stats["escrow_locked"] == PAYOUT + PREMIUM

    # Settlement is gated until the coverage window fully ends: with the
    # window still live, it must revert. (The deterministic settlement path
    # itself is proven by the direct-mode tests; live demo policies settle
    # once their windows end.) A revert surfaces either as an exception or as
    # a receipt whose execution failed, so accept both.
    reverted = False
    try:
        receipt = contract.settle_policy(args=[1]).transact(
            wait_interval=10000, wait_retries=5
        )
        reverted = not tx_execution_succeeded(receipt)
    except Exception as e:
        reverted = "coverage window has not ended yet" in str(e)
    assert reverted, "settle_policy should have reverted mid-window"

    policy = contract.get_policy(args=[1]).call()
    assert policy["status"] == "ACTIVE"  # untouched by the failed settle
    assert policy["attempts"] == 0


@pytest.mark.integration
def test_views_reflect_policy_state_and_typed_addresses():
    accounts = get_accounts()
    insurer = accounts[2]
    contract = _deploy(account=insurer)

    # Two policies so personal lists and pagination can be observed.
    receipt = contract.create_policy(
        args=[
            "rainfall", LAT, LON, _today_str(), _in_days(1),
            THRESHOLD, "below", 50, 150,
        ],
    ).transact(value=150, wait_interval=10000, wait_retries=15)
    assert tx_execution_succeeded(receipt)
    receipt = contract.create_policy(
        args=[
            "temperature", "1.35", "103.82", _today_str(), _in_days(2),
            "35.0", "above", 80, 240,
        ],
    ).transact(value=240, wait_interval=10000, wait_retries=15)
    assert tx_execution_succeeded(receipt)

    # list_policies exposes both, newest last.
    listed = contract.list_policies(args=[0, 50]).call()
    assert len(listed) == 2
    assert [p["id"] for p in listed] == [1, 2]
    assert listed[0]["metric"] == "rainfall"
    assert listed[1]["metric"] == "temperature"

    # Address-typed args must be encoded as addresses (CalldataAddress); a
    # plain hex string is sent as text and fails the VM's TreeMap lookup.
    mine = contract.list_insurer_policies(
        args=[CalldataAddress(insurer.address), 0, 50]
    ).call()
    assert len(mine) == 2
    assert contract.list_buyer_policies(
        args=[CalldataAddress(insurer.address), 0, 50]
    ).call() == []

    stats = contract.get_stats(args=[]).call()
    assert stats["total_policies"] == 2
    assert stats["open"] == 2
    assert stats["escrow_locked"] == 150 + 240
