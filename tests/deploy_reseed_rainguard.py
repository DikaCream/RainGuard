"""Deploy a fresh RainGuard and seed demo policies with real GEN amounts.

Prints the new contract address for the frontend + README update.
Run: .venv/bin/gltest --network studionet tests/deploy_reseed_rainguard.py -v -s
"""

import datetime

from gltest import get_accounts, get_contract_factory
from gltest.assertions import tx_execution_succeeded

GEN = 10**18


def _day(offset_days: int) -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=offset_days)
    ).strftime("%Y-%m-%d")


def test_deploy_and_seed():
    accounts = get_accounts()
    insurer, buyer = accounts[0], accounts[1]

    factory = get_contract_factory("RainGuard")
    contract = factory.deploy(account=insurer)
    address = contract.address
    print(f"\nNEW CONTRACT ADDRESS: {address}\n")

    # Policy 1 — OPEN, Jakarta rainfall drought cover (below 8mm), so a
    # visitor can actually buy it from the live board.
    receipt = contract.create_policy(
        args=[
            "rainfall", "-6.2", "106.8", _day(0), _day(4),
            "8.0", "below", 5 * 10**17, 5 * GEN,
        ],
    ).transact(value=5 * GEN, wait_interval=10000, wait_retries=15)
    assert tx_execution_succeeded(receipt), receipt
    print("policy 1 (OPEN, rainfall, payout 5 GEN): OK")

    # Policy 2 — Singapore temperature heatwave cover, bought -> ACTIVE.
    receipt = contract.create_policy(
        args=[
            "temperature", "1.35", "103.82", _day(0), _day(2),
            "33.5", "above", 3 * 10**17, 3 * GEN,
        ],
    ).transact(value=3 * GEN, wait_interval=10000, wait_retries=15)
    assert tx_execution_succeeded(receipt), receipt
    print("policy 2 (OPEN, temperature, payout 3 GEN): OK")

    receipt = contract.connect(buyer).buy_policy(
        args=[2],
    ).transact(value=3 * 10**17, wait_interval=10000, wait_retries=15)
    assert tx_execution_succeeded(receipt), receipt
    print("policy 2 bought -> ACTIVE: OK")

    stats = contract.get_stats(args=[]).call()
    print(f"\nSTATS: total={stats['total_policies']} open={stats['open']} "
          f"active={stats['active']} escrow={stats['escrow_locked'] / GEN} GEN")
    print(f"\nUSE THIS ADDRESS: {address}")
