"""RainGuard direct-mode tests — deterministic weather settlement, escrow, fail-closed."""

import json

from tests.direct.conftest import (
    RG_END_DATE,
    RG_START_DATE,
    addr,
    create_policy,
    funded_policy,
    iso_to_ts,
    mock_weather,
    set_time,
    to_hex,
)

# Settlement is eligible the day after END_DATE + 1h buffer (see contract).
# RG_END_DATE is 2030-01-05, so eligibility is 2030-01-06T01:00:00Z.
SETTLE_ELIGIBLE_ISO = "2030-01-06T01:00:00Z"
SETTLE_ELIGIBLE_TS = iso_to_ts(SETTLE_ELIGIBLE_ISO)


# ---------------------------------------------------------------- happy paths
def test_drought_trigger_pays_buyer(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/rain_guard.py")
    pid = funded_policy(
        contract, direct_vm, direct_alice, direct_bob,
        metric="rainfall", threshold="2.0", condition="below",  # sum 1.5 < 2
    )

    p = contract.get_policy(pid)
    assert p["status"] == "ACTIVE"
    assert p["buyer"].lower() == to_hex(direct_bob).lower()
    assert contract.get_config()["escrow_locked"] == 300  # payout 200 + premium 100

    set_time(SETTLE_ELIGIBLE_ISO)
    mock_weather(direct_vm)
    contract.settle_policy(pid)
    direct_vm.clear_mocks()

    p = contract.get_policy(pid)
    assert p["status"] == "PAID"
    assert p["measured"] == "1.5"
    assert contract.get_config()["escrow_locked"] == 0


def test_missed_trigger_expires_to_insurer(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/rain_guard.py")
    pid = funded_policy(
        contract, direct_vm, direct_alice, direct_bob,
        metric="rainfall", threshold="1.0", condition="below",  # sum 1.5 >= 1
    )

    set_time(SETTLE_ELIGIBLE_ISO)
    mock_weather(direct_vm)
    contract.settle_policy(pid)

    p = contract.get_policy(pid)
    assert p["status"] == "EXPIRED"
    assert p["measured"] == "1.5"
    assert contract.get_config()["escrow_locked"] == 0


def test_heatwave_trigger_pays_buyer(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/rain_guard.py")
    # Daily max temps in the mock are [31.5, 30.2]; max = 31.5.
    pid = funded_policy(
        contract, direct_vm, direct_alice, direct_bob,
        metric="temperature", threshold="31.0", condition="above",
    )

    set_time(SETTLE_ELIGIBLE_ISO)
    mock_weather(direct_vm)
    contract.settle_policy(pid)

    p = contract.get_policy(pid)
    assert p["status"] == "PAID"
    assert p["measured"] == "31.5"


def test_cold_snap_pays_when_max_below_threshold(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/rain_guard.py")
    # max temp 31.5 IS below 32.0, so the cold-snap trigger hit.
    pid = funded_policy(
        contract, direct_vm, direct_alice, direct_bob,
        metric="temperature", threshold="32.0", condition="below",
    )

    set_time(SETTLE_ELIGIBLE_ISO)
    mock_weather(direct_vm)
    contract.settle_policy(pid)

    assert contract.get_policy(pid)["status"] == "PAID"


def test_heatwave_expires_when_max_below_threshold(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/rain_guard.py")
    # max temp 31.5 is NOT above 35.0, so the heatwave trigger missed.
    pid = funded_policy(
        contract, direct_vm, direct_alice, direct_bob,
        metric="temperature", threshold="35.0", condition="above",
    )

    set_time(SETTLE_ELIGIBLE_ISO)
    mock_weather(direct_vm)
    contract.settle_policy(pid)

    assert contract.get_policy(pid)["status"] == "EXPIRED"


# ---------------------------------------------------------------- creation rules
def test_create_wrong_value_reverts(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/rain_guard.py")
    direct_vm.sender = direct_alice
    direct_vm.value = 50
    with direct_vm.expect_revert("exact payout must be sent"):
        contract.create_policy(
            "rainfall", "-6.2", "106.8", RG_START_DATE, RG_END_DATE,
            "2.0", "below", 100, 200,
        )
    direct_vm.value = 0


def test_create_zero_payout_reverts(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/rain_guard.py")
    direct_vm.sender = direct_alice
    direct_vm.value = 0
    with direct_vm.expect_revert("payout must be greater than zero"):
        contract.create_policy(
            "rainfall", "-6.2", "106.8", RG_START_DATE, RG_END_DATE,
            "2.0", "below", 100, 0,
        )


def test_create_zero_premium_reverts(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/rain_guard.py")
    direct_vm.sender = direct_alice
    direct_vm.value = 200
    with direct_vm.expect_revert("premium must be greater than zero"):
        contract.create_policy(
            "rainfall", "-6.2", "106.8", RG_START_DATE, RG_END_DATE,
            "2.0", "below", 0, 200,
        )
    direct_vm.value = 0


def test_create_bad_metric_reverts(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/rain_guard.py")
    direct_vm.sender = direct_alice
    direct_vm.value = 200
    with direct_vm.expect_revert("metric must be rainfall or temperature"):
        contract.create_policy(
            "wind", "-6.2", "106.8", RG_START_DATE, RG_END_DATE,
            "2.0", "below", 100, 200,
        )
    direct_vm.value = 0


def test_create_bad_coords_reverts(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/rain_guard.py")
    for lat, lon, msg in (
        ("91.0", "0", "lat must be a decimal"),
        ("-6.2", "181.0", "lon must be a decimal"),
        ("abc", "106.8", "lat must be a decimal"),
    ):
        direct_vm.sender = direct_alice
        direct_vm.value = 200
        with direct_vm.expect_revert(msg):
            contract.create_policy(
                "rainfall", lat, lon, RG_START_DATE, RG_END_DATE,
                "2.0", "below", 100, 200,
            )
    direct_vm.value = 0


def test_create_bad_dates_reverts(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/rain_guard.py")
    for start, end, msg in (
        ("2030-02-01", "2030-01-10", "end_date must not be before start_date"),
        ("not-a-date", "2030-01-10", "dates must be YYYY-MM-DD"),
    ):
        direct_vm.sender = direct_alice
        direct_vm.value = 200
        with direct_vm.expect_revert(msg):
            contract.create_policy(
                "rainfall", "-6.2", "106.8", start, end, "2.0", "below", 100, 200,
            )
    direct_vm.value = 0


def test_create_past_window_reverts(direct_vm, direct_deploy, direct_alice):
    """A window that already ended is dead on arrival — it could never be
    bought (the outcome is knowable), so creation rejects it outright."""
    contract = direct_deploy("contracts/rain_guard.py")
    # Pin block time to a known instant AFTER the deploy import, so the
    # contract's _now() is deterministic regardless of wall-clock time.
    set_time("2030-01-10T00:00:00Z")
    direct_vm.sender = direct_alice
    direct_vm.value = 200
    # 2030-01-01..2030-01-05 ended well before pinned now (2030-01-10).
    with direct_vm.expect_revert("end_date must be today or later"):
        contract.create_policy(
            "rainfall", "-6.2", "106.8", "2030-01-01", "2030-01-05",
            "2.0", "below", 100, 200,
        )
    direct_vm.value = 0


def test_create_window_too_long_reverts(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/rain_guard.py")
    direct_vm.sender = direct_alice
    direct_vm.value = 200
    with direct_vm.expect_revert("window must be 31 days or less"):
        contract.create_policy(
            "rainfall", "-6.2", "106.8", "2030-01-01", "2030-03-01",
            "2.0", "below", 100, 200,
        )
    direct_vm.value = 0


def test_create_bad_threshold_and_condition_revert(
    direct_vm, direct_deploy, direct_alice
):
    contract = direct_deploy("contracts/rain_guard.py")
    direct_vm.sender = direct_alice
    direct_vm.value = 200
    with direct_vm.expect_revert("threshold must be a positive decimal"):
        contract.create_policy(
            "rainfall", "-6.2", "106.8", RG_START_DATE, RG_END_DATE,
            "-1", "below", 100, 200,
        )
    direct_vm.value = 0
    direct_vm.value = 200
    with direct_vm.expect_revert("condition must be below or above"):
        contract.create_policy(
            "rainfall", "-6.2", "106.8", RG_START_DATE, RG_END_DATE,
            "2.0", "exactly", 100, 200,
        )
    direct_vm.value = 0


# ---------------------------------------------------------------- buying rules
def test_buy_wrong_premium_reverts(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/rain_guard.py")
    pid = create_policy(contract, direct_vm, direct_alice)

    direct_vm.sender = direct_bob
    direct_vm.value = 99
    with direct_vm.expect_revert("exact premium must be sent"):
        contract.buy_policy(pid)
    direct_vm.value = 0


def test_buy_own_policy_reverts(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/rain_guard.py")
    pid = create_policy(contract, direct_vm, direct_alice)

    direct_vm.sender = direct_alice
    direct_vm.value = 100
    with direct_vm.expect_revert("insurer cannot buy their own policy"):
        contract.buy_policy(pid)
    direct_vm.value = 0


def test_buy_twice_reverts(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = direct_deploy("contracts/rain_guard.py")
    pid = create_policy(contract, direct_vm, direct_alice)

    direct_vm.sender = direct_bob
    direct_vm.value = 100
    contract.buy_policy(pid)
    direct_vm.value = 0

    direct_vm.sender = direct_charlie
    direct_vm.value = 100
    with direct_vm.expect_revert("policy is not open for purchase"):
        contract.buy_policy(pid)
    direct_vm.value = 0


def test_buy_on_final_second_of_window_still_allowed(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """Buying closes at midnight AFTER the last covered day, not before it: a
    buyer may still take coverage on the window's final second, because the
    outcome is not knowable until that day is over."""
    contract = direct_deploy("contracts/rain_guard.py")
    pid = create_policy(contract, direct_vm, direct_alice)

    # 2030-01-05T23:59:59Z — the last second of the coverage window's final
    # day (window is 2030-01-01..2030-01-05). Buying must still succeed.
    set_time("2030-01-05T23:59:59Z")
    direct_vm.sender = direct_bob
    direct_vm.value = 100
    contract.buy_policy(pid)
    direct_vm.value = 0
    assert contract.get_policy(pid)["status"] == "ACTIVE"

    # One second later the window is over and the outcome is knowable:
    # the same policy can no longer be bought.
    set_time("2030-01-06T00:00:00Z")
    pid2 = create_policy(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_bob
    direct_vm.value = 100
    with direct_vm.expect_revert("coverage window has ended"):
        contract.buy_policy(pid2)
    direct_vm.value = 0


def test_trigger_equality_never_pays(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """A trigger is strict on both sides: measured == threshold does not hit.
    A drought cover at exactly the threshold is not drier, a heatwave cover at
    exactly the threshold is not hotter. Only crossing the number pays."""
    contract = direct_deploy("contracts/rain_guard.py")
    # Sum of mock rainfall is exactly 1.5; a "below 1.5" drought must MISS.
    pid = funded_policy(
        contract, direct_vm, direct_alice, direct_bob,
        metric="rainfall", threshold="1.5", condition="below",
    )
    # Max mock temperature is exactly 31.5; an "above 31.5" heatwave MISSES.
    # Both policies are created while the window is still live, then both
    # settle once it ends.
    pid2 = funded_policy(
        contract, direct_vm, direct_alice, direct_bob,
        metric="temperature", threshold="31.5", condition="above",
    )
    set_time(SETTLE_ELIGIBLE_ISO)
    mock_weather(direct_vm)
    contract.settle_policy(pid)
    contract.settle_policy(pid2)
    assert contract.get_policy(pid)["status"] == "EXPIRED"
    assert contract.get_policy(pid2)["status"] == "EXPIRED"


def test_buy_after_window_end_reverts_and_never_settles(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """A stale OPEN policy is frozen at the end of its coverage window: it can
    no longer be bought (the outcome is already knowable from public weather
    data), so it can never be bought and immediately settled. The insurer's
    only way out is cancel_policy."""
    contract = direct_deploy("contracts/rain_guard.py")
    pid = create_policy(contract, direct_vm, direct_alice)

    # Well after RG_END_DATE (2030-01-05): the window is over.
    set_time("2030-01-10T00:00:00Z")
    direct_vm.sender = direct_bob
    direct_vm.value = 100
    with direct_vm.expect_revert("coverage window has ended"):
        contract.buy_policy(pid)
    direct_vm.value = 0

    p = contract.get_policy(pid)
    assert p["status"] == "OPEN"
    assert p["buyer"] == ""
    # Never funded by a second party -> settlement is blocked too.
    mock_weather(direct_vm)
    with direct_vm.expect_revert("policy is not active"):
        contract.settle_policy(pid)
    assert contract.get_config()["escrow_locked"] == 200  # payout still held

    # The insurer can still cancel and recover the payout.
    direct_vm.sender = direct_alice
    contract.cancel_policy(pid)
    assert contract.get_policy(pid)["status"] == "CANCELLED"
    assert contract.get_config()["escrow_locked"] == 0


# ---------------------------------------------------------------- cancellation
def test_cancel_only_insurer_and_only_open(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/rain_guard.py")
    pid = create_policy(contract, direct_vm, direct_alice)

    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("only the insurer can cancel the policy"):
        contract.cancel_policy(pid)

    direct_vm.sender = direct_alice
    contract.cancel_policy(pid)
    assert contract.get_policy(pid)["status"] == "CANCELLED"
    assert contract.get_config()["escrow_locked"] == 0

    with direct_vm.expect_revert("only an open policy can be cancelled"):
        contract.cancel_policy(pid)


def test_cancel_open_policy_after_window_end(direct_vm, direct_deploy, direct_alice):
    """An OPEN policy can never settle once its window is over; the insurer
    must be able to recover the payout."""
    contract = direct_deploy("contracts/rain_guard.py")
    pid = create_policy(contract, direct_vm, direct_alice)

    set_time("2030-01-10T00:00:00Z")
    with direct_vm.expect_revert("policy is not active"):
        contract.settle_policy(pid)
    direct_vm.sender = direct_alice
    contract.cancel_policy(pid)
    assert contract.get_policy(pid)["status"] == "CANCELLED"
    assert contract.get_config()["escrow_locked"] == 0


# ---------------------------------------------------------------- settlement rules
def test_settle_before_eligible_reverts(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/rain_guard.py")
    pid = funded_policy(contract, direct_vm, direct_alice, direct_bob)

    # Block time is within the coverage window (base is 2030-01-01).
    mock_weather(direct_vm)
    with direct_vm.expect_revert("coverage window has not ended yet"):
        contract.settle_policy(pid)


def test_settle_when_open_reverts(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/rain_guard.py")
    pid = create_policy(contract, direct_vm, direct_alice)

    set_time(SETTLE_ELIGIBLE_ISO)
    mock_weather(direct_vm)
    with direct_vm.expect_revert("policy is not active"):
        contract.settle_policy(pid)


def test_double_settle_reverts(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/rain_guard.py")
    pid = funded_policy(contract, direct_vm, direct_alice, direct_bob)

    set_time(SETTLE_ELIGIBLE_ISO)
    mock_weather(direct_vm)
    contract.settle_policy(pid)
    direct_vm.clear_mocks()

    with direct_vm.expect_revert("policy is not active"):
        contract.settle_policy(pid)


def test_failed_settlement_stays_active_then_retry(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/rain_guard.py")
    pid = funded_policy(contract, direct_vm, direct_alice, direct_bob)

    set_time(SETTLE_ELIGIBLE_ISO)
    # Validators get unusable weather -> fail closed, money untouched.
    direct_vm.mock_web(
        r".*archive-api\.open-meteo\.com.*",
        {"status": 200, "body": "not json at all"},
    )
    contract.settle_policy(pid)
    direct_vm.clear_mocks()

    p = contract.get_policy(pid)
    assert p["status"] == "ACTIVE"  # fail closed
    assert p["attempts"] == 1
    assert contract.get_config()["escrow_locked"] == 300

    # Cooldown: an immediate retry reverts.
    mock_weather(direct_vm)
    with direct_vm.expect_revert("settlement was just attempted"):
        contract.settle_policy(pid)

    # After the cooldown the retry succeeds.
    set_time("2030-01-08T00:05:00Z")
    contract.settle_policy(pid)
    assert contract.get_policy(pid)["status"] == "PAID"
    assert contract.get_config()["escrow_locked"] == 0


def test_retry_limit_then_stale_close_refunds_both(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = direct_deploy("contracts/rain_guard.py")
    pid = funded_policy(contract, direct_vm, direct_alice, direct_bob)

    set_time(SETTLE_ELIGIBLE_ISO)
    for i in range(5):
        direct_vm.mock_web(
            r".*archive-api\.open-meteo\.com.*",
            {"status": 200, "body": "not json at all"},
        )
        contract.settle_policy(pid)
        direct_vm.clear_mocks()
        set_time(f"2030-01-08T00:{5 * (i + 1):02d}:00Z")  # past cooldown each time

    p = contract.get_policy(pid)
    assert p["status"] == "ACTIVE"
    assert p["attempts"] == 5
    assert contract.get_config()["escrow_locked"] == 300

    mock_weather(direct_vm)
    with direct_vm.expect_revert("settlement retry limit reached"):
        contract.settle_policy(pid)

    # 7 days past settle eligibility (2030-01-08 01:00 + 7d = 2030-01-15 01:00).
    set_time("2030-01-15T01:00:00Z")
    direct_vm.sender = direct_charlie  # anyone may close
    contract.close_stale_policy(pid)

    p = contract.get_policy(pid)
    assert p["status"] == "REFUNDED"
    assert contract.get_config()["escrow_locked"] == 0


def test_stale_close_before_stale_window_reverts(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/rain_guard.py")
    pid = funded_policy(contract, direct_vm, direct_alice, direct_bob)

    set_time(SETTLE_ELIGIBLE_ISO)
    with direct_vm.expect_revert("policy is not stale yet"):
        contract.close_stale_policy(pid)


# ---------------------------------------------------------------- escrow accounting
def test_escrow_accounting_multiple_policies(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/rain_guard.py")
    p1 = create_policy(contract, direct_vm, direct_alice, payout=200, premium=100)
    p2 = create_policy(contract, direct_vm, direct_bob, payout=500, premium=250)
    assert contract.get_config()["escrow_locked"] == 700

    # Bob buys alice's policy -> +100 premium.
    direct_vm.sender = direct_bob
    direct_vm.value = 100
    contract.buy_policy(p1)
    direct_vm.value = 0
    assert contract.get_config()["escrow_locked"] == 800

    # Bob cancels his own open policy -> -500.
    direct_vm.sender = direct_bob
    contract.cancel_policy(p2)
    assert contract.get_config()["escrow_locked"] == 300

    # Settle p1 (trigger hit) -> -(200 + 100).
    set_time(SETTLE_ELIGIBLE_ISO)
    mock_weather(direct_vm)
    contract.settle_policy(p1)
    assert contract.get_config()["escrow_locked"] == 0


# ---------------------------------------------------------------- views
def test_views(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/rain_guard.py")

    assert contract.get_policy(1) is None
    assert contract.get_config()["policy_count"] == 0
    assert contract.get_stats()["total_policies"] == 0

    pid = funded_policy(contract, direct_vm, direct_alice, direct_bob)
    p = contract.get_policy(pid)
    assert p["metric"] == "rainfall"
    assert p["lat"] == "-6.2"
    assert p["premium"] == 100
    assert p["payout"] == 200
    assert p["status"] == "ACTIVE"
    # settle-eligible: end 2030-01-05 + 1 day + 1h
    assert p["settle_eligible_at"] == SETTLE_ELIGIBLE_TS

    assert contract.list_policies(0, 10)[0]["id"] == pid
    assert contract.list_policies(1, 10) == []
    assert contract.list_policies(0, 0) == []

    stats = contract.get_stats()
    assert stats["total_policies"] == 1
    assert stats["active"] == 1
    assert stats["escrow_locked"] == 300


def test_personal_policy_lists_are_address_scoped(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """list_insurer_policies / list_buyer_policies key on the exact typed
    Address: each party only sees the policies they took part in, and a
    stranger's Address resolves to empty lists on both sides."""
    contract = direct_deploy("contracts/rain_guard.py")
    p1 = funded_policy(contract, direct_vm, direct_alice, direct_bob)

    # Alice insurers a second policy; Charlie buys it.
    direct_vm.sender = direct_alice
    direct_vm.value = 300
    p2 = int(contract.create_policy(
        "temperature", "1.35", "103.82", RG_START_DATE, RG_END_DATE,
        "31.0", "above", 150, 300,
    ))
    direct_vm.value = 0
    direct_vm.sender = direct_charlie
    direct_vm.value = 150
    contract.buy_policy(p2)
    direct_vm.value = 0

    assert [p["id"] for p in contract.list_insurer_policies(addr(direct_alice), 0, 10)] == [p1, p2]
    assert contract.list_insurer_policies(addr(direct_bob), 0, 10) == []
    assert contract.list_insurer_policies(addr(direct_charlie), 0, 10) == []

    assert [p["id"] for p in contract.list_buyer_policies(addr(direct_bob), 0, 10)] == [p1]
    assert [p["id"] for p in contract.list_buyer_policies(addr(direct_charlie), 0, 10)] == [p2]
    assert contract.list_buyer_policies(addr(direct_alice), 0, 10) == []

    # Pagination applies on personal lists too.
    assert [p["id"] for p in contract.list_insurer_policies(addr(direct_alice), 1, 10)] == [p2]
    assert contract.list_buyer_policies(addr(direct_bob), 1, 10) == []


def test_measured_value_and_terminal_statuses_persist(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/rain_guard.py")
    pid = funded_policy(
        contract, direct_vm, direct_alice, direct_bob,
        metric="rainfall", threshold="2.0", condition="below",
    )

    set_time(SETTLE_ELIGIBLE_ISO)
    mock_weather(direct_vm)
    contract.settle_policy(pid)

    p = contract.get_policy(pid)
    assert p["status"] == "PAID"
    assert p["measured"] == "1.5"
    assert p["attempts"] == 1

    stats = contract.get_stats()
    assert stats["paid"] == 1
    assert stats["active"] == 0
    assert stats["escrow_locked"] == 0
