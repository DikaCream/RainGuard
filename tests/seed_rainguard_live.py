"""Deploy RainGuard to StudioNet and seed live demo policies.

Run with: gltest --network studionet tests/seed_rainguard_live.py -v -s

Prints the deployed contract address at the end; copy it into
frontend-rainguard/src/config.ts / the Vercel env var.
"""

import datetime
import sys

import pytest
from gltest import get_accounts, get_contract_factory
from gltest.assertions import tx_execution_succeeded


def _in_days(days: int) -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=days)
    ).strftime("%Y-%m-%d")


@pytest.mark.integration
def test_deploy_and_seed_demo_policies():
    accounts = get_accounts()
    insurer = accounts[0]
    buyer = accounts[1]
    assert insurer.address != buyer.address

    factory = get_contract_factory("RainGuard")
    contract = factory.deploy(account=insurer)
    print(f"\nDEPLOYED RainGuard at: {contract.address}", flush=True)

    def create(metric, lat, lon, end_days, threshold, condition, premium, payout, buyer_idx):
        """Create today..+end_days policy and buy it with another account."""
        start = _in_days(0)
        end = _in_days(end_days)
        receipt = contract.create_policy(
            args=[metric, lat, lon, start, end, threshold, condition, premium, payout],
        ).transact(value=payout, wait_interval=10000, wait_retries=20)
        assert tx_execution_succeeded(receipt), "create_policy failed"

        me = contract.connect(accounts[buyer_idx])
        receipt = me.buy_policy(
            args=[contract.get_stats(args=[]).call()["total_policies"]],
        ).transact(value=premium, wait_interval=10000, wait_retries=20)
        assert tx_execution_succeeded(receipt), "buy_policy failed"
        print(
            f"  seeded {metric} {condition} {threshold} @({lat},{lon}) "
            f"{start}..{end} premium={premium} payout={payout}",
            flush=True,
        )

    # 1. Jakarta rainfall sum below 8mm over the window (drought cover).
    #    Jakarta's dry-season daily totals hover around 0-2mm; a dry stretch
    #    pays the buyer, a storm pushes the sum over and expires.
    create("rainfall", "-6.2", "106.8", 3, "8.0", "below", 2, 15, 1)

    # 2. Singapore max temperature above 33.5C (heatwave cover). Daily maxes
    #    sit near 32C; a strong sun day pays the buyer.
    create("temperature", "1.35", "103.82", 2, "33.5", "above", 1, 8, 2)

    print(f"\nCONTRACT ADDRESS: {contract.address}", flush=True)
