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
# RG_END_DATE is 2030-01-06, so eligibility is 2030-01-07T01:00:00Z.
SETTLE_ELIGIBLE_ISO = "2030-01-07T01:00:00Z"
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
    """A window that has already begun is dead on arrival — the weather is
    already happening, so creation rejects it outright."""
    contract = direct_deploy("contracts/rain_guard.py")
    # Pin block time to a known instant AFTER the deploy import, so the
    # contract's _now() is deterministic regardless of wall-clock time.
    set_time("2030-01-10T00:00:00Z")
    direct_vm.sender = direct_alice
    direct_vm.value = 200
    # 2030-01-01..2030-01-05 began well before pinned now (2030-01-10).
    with direct_vm.expect_revert("coverage must not have begun yet"):
        contract.create_policy(
            "rainfall", "-6.2", "106.8", "2030-01-01", "2030-01-05",
            "2.0", "below", 100, 200,
        )
    direct_vm.value = 0


def test_create_closes_at_the_moment_coverage_begins(
    direct_vm, direct_deploy, direct_alice
):
    """Creation is allowed in the final second before the window opens and
    reverts the instant it opens."""
    contract = direct_deploy("contracts/rain_guard.py")
    # Window starts 2030-01-02T00:00:00Z. At 23:59:59 on 01-01 creation is
    # still allowed...
    set_time("2030-01-01T23:59:59Z")
    pid = create_policy(contract, direct_vm, direct_alice)
    assert contract.get_policy(pid)["status"] == "OPEN"
    # ...and at 00:00:00 on 01-02 it reverts: coverage has begun.
    set_time("2030-01-02T00:00:00Z")
    direct_vm.sender = direct_alice
    direct_vm.value = 200
    with direct_vm.expect_revert("coverage must not have begun yet"):
        contract.create_policy(
            "rainfall", "-6.2", "106.8", RG_START_DATE, RG_END_DATE,
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


def test_buy_closes_the_moment_coverage_begins(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """Buying closes when the coverage window OPENS: a buyer may still take
    coverage in the final second before the window starts, and one second
    later — the moment the weather begins — the same policy can no longer be
    bought."""
    contract = direct_deploy("contracts/rain_guard.py")
    pid = create_policy(contract, direct_vm, direct_alice)
    pid2 = create_policy(contract, direct_vm, direct_alice)

    # 2030-01-01T23:59:59Z — the last second before the coverage window opens
    # on 2030-01-02T00:00:00Z. Buying must still succeed.
    set_time("2030-01-01T23:59:59Z")
    direct_vm.sender = direct_bob
    direct_vm.value = 100
    contract.buy_policy(pid)
    direct_vm.value = 0
    assert contract.get_policy(pid)["status"] == "ACTIVE"

    # One second later the window has begun and the weather is happening:
    # the second policy can no longer be bought.
    set_time("2030-01-02T00:00:00Z")
    direct_vm.sender = direct_bob
    direct_vm.value = 100
    with direct_vm.expect_revert("coverage has already begun"):
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
    # Both policies are created before the window opens, then both settle
    # once it ends.
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


def test_buy_after_coverage_begins_reverts_and_never_settles(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """A stale OPEN policy is frozen the moment its coverage window opens: it
    can no longer be bought (the weather is already happening, so the outcome
    is partly knowable), meaning it can never be bought and immediately
    settled. The insurer's only way out is cancel_policy."""
    contract = direct_deploy("contracts/rain_guard.py")
    pid = create_policy(contract, direct_vm, direct_alice)

    # Well after RG_START_DATE (2030-01-02): the coverage has begun.
    set_time("2030-01-10T00:00:00Z")
    direct_vm.sender = direct_bob
    direct_vm.value = 100
    with direct_vm.expect_revert("coverage has already begun"):
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

    # Block time (base 2030-01-01) is well before the window even opens, so
    # settlement is far from eligible.
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
    direct_vm.clear_mocks()

    # After the cooldown the retry succeeds on the correct archive.
    set_time("2030-01-08T00:05:00Z")
    mock_weather(direct_vm)
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


def test_stale_close_requires_exhausted_retries_and_stale_window(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """Stale closure is gated TWICE: the retry path must be genuinely
    exhausted (MAX_SETTLE_ATTEMPTS recorded failures) AND the stale window
    must have passed. A policy with no recorded settle attempt cannot be
    closed stale even after its settle-eligible time; one that exhausted its
    retries still cannot be closed before the stale window passes."""
    contract = direct_deploy("contracts/rain_guard.py")
    pid = funded_policy(contract, direct_vm, direct_alice, direct_bob)

    # Settlement is eligible but no attempt is recorded yet: stale closure
    # must revert — the retry path has not been exhausted.
    set_time(SETTLE_ELIGIBLE_ISO)
    with direct_vm.expect_revert("settlement retries not exhausted"):
        contract.close_stale_policy(pid)

    # Exhaust the retry path: 5 failed settle attempts (past cooldown each).
    for i in range(5):
        direct_vm.mock_web(
            r".*archive-api\.open-meteo\.com.*",
            {"status": 200, "body": "not json at all"},
        )
        contract.settle_policy(pid)
        direct_vm.clear_mocks()
        set_time(f"2030-01-08T00:{5 * (i + 1):02d}:00Z")
    p = contract.get_policy(pid)
    assert p["status"] == "ACTIVE"
    assert p["attempts"] == 5

    # Attempts exhausted but the stale window (eligible + 7d = 2030-01-14
    # 01:00) has not passed yet: still gated.
    with direct_vm.expect_revert("policy is not stale yet"):
        contract.close_stale_policy(pid)

    # Past the stale window with retries exhausted: anyone may close it.
    set_time("2030-01-15T01:00:00Z")
    direct_vm.sender = direct_charlie
    contract.close_stale_policy(pid)
    assert contract.get_policy(pid)["status"] == "REFUNDED"
    assert contract.get_config()["escrow_locked"] == 0


# ------------------------------------------------- settlement source validation
# Settlement must only move money on the UTC archive for the policy's exact
# coordinates and exact covered dates. Each test below serves a wrong-but-
# plausible response, asserts the policy fails CLOSED (ACTIVE, escrow
# untouched, one attempt recorded), then proves a retry against the correct
# archive settles normally.


def _source_rejected_fails_closed(contract, vm, pid):
    """Shared assertions after a settlement that rejected the source."""
    p = contract.get_policy(pid)
    assert p["status"] == "ACTIVE"  # fail closed
    assert p["attempts"] == 1
    assert p["measured"] == ""
    assert contract.get_config()["escrow_locked"] == 300
    # A retry against the correct archive settles the policy.
    vm.clear_mocks()
    set_time("2030-01-08T00:05:00Z")  # past the settle cooldown
    mock_weather(vm)
    contract.settle_policy(pid)
    assert contract.get_policy(pid)["status"] == "PAID"


def test_settlement_rejects_wrong_coordinates(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """The archive echoes the coordinate it was queried for; a response from a
    different grid point (here northern-hemisphere Jakarta) is rejected."""
    contract = direct_deploy("contracts/rain_guard.py")
    pid = funded_policy(contract, direct_vm, direct_alice, direct_bob)

    set_time(SETTLE_ELIGIBLE_ISO)
    mock_weather(direct_vm, lat="6.2")  # policy is -6.2
    contract.settle_policy(pid)
    _source_rejected_fails_closed(contract, direct_vm, pid)


def test_settlement_rejects_wrong_longitude(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/rain_guard.py")
    pid = funded_policy(contract, direct_vm, direct_alice, direct_bob)

    set_time(SETTLE_ELIGIBLE_ISO)
    mock_weather(direct_vm, lon="1.0")  # policy is 106.8
    contract.settle_policy(pid)
    _source_rejected_fails_closed(contract, direct_vm, pid)


def test_settlement_rejects_wrong_timezone(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """The archive must be the UTC series: a local-timezone series shifts the
    calendar days and must never settle a policy."""
    contract = direct_deploy("contracts/rain_guard.py")
    pid = funded_policy(contract, direct_vm, direct_alice, direct_bob)

    set_time(SETTLE_ELIGIBLE_ISO)
    mock_weather(direct_vm, tz="Asia/Jakarta")
    contract.settle_policy(pid)
    _source_rejected_fails_closed(contract, direct_vm, pid)


def test_settlement_rejects_wrong_dates(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """The returned dates must be the policy's exact covered days. A series
    shifted by one day (2030-01-03..07 instead of 01-02..06) is rejected even
    though the row count and values are identical."""
    contract = direct_deploy("contracts/rain_guard.py")
    pid = funded_policy(contract, direct_vm, direct_alice, direct_bob)

    set_time(SETTLE_ELIGIBLE_ISO)
    mock_weather(
        direct_vm, days=[f"2030-01-{d:02d}" for d in range(3, 8)],
    )
    contract.settle_policy(pid)
    _source_rejected_fails_closed(contract, direct_vm, pid)


def test_settlement_rejects_wrong_row_count(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """Row count must equal the number of covered days: a truncated series
    (4 rows for a 5-day window) is rejected."""
    contract = direct_deploy("contracts/rain_guard.py")
    pid = funded_policy(contract, direct_vm, direct_alice, direct_bob)

    set_time(SETTLE_ELIGIBLE_ISO)
    mock_weather(
        direct_vm, days=[f"2030-01-{d:02d}" for d in range(2, 6)],
    )
    contract.settle_policy(pid)
    _source_rejected_fails_closed(contract, direct_vm, pid)


def test_settlement_rejects_incomplete_metric_data(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """The metric column must cover every covered day with a real number: a
    precipitation series with only 3 of the 5 days is rejected."""
    contract = direct_deploy("contracts/rain_guard.py")
    pid = funded_policy(contract, direct_vm, direct_alice, direct_bob)

    set_time(SETTLE_ELIGIBLE_ISO)
    mock_weather(direct_vm, precip=[0.3, 0.2, 0.5])
    contract.settle_policy(pid)
    _source_rejected_fails_closed(contract, direct_vm, pid)


def test_settlement_rejects_missing_metric_column(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """A response without the metric column at all (here temperature on a
    rainfall policy) is rejected."""
    contract = direct_deploy("contracts/rain_guard.py")
    pid = funded_policy(contract, direct_vm, direct_alice, direct_bob)

    set_time(SETTLE_ELIGIBLE_ISO)
    body = json.dumps(
        {
            "latitude": -6.2,
            "longitude": 106.8,
            "timezone": "UTC",
            "daily": {
                "time": [f"2030-01-{d:02d}" for d in range(2, 7)],
                "precipitation_sum": None,
                "temperature_2m_max": [29.0, 30.1, 31.5, 28.4, 30.2],
            },
        }
    )
    direct_vm.mock_web(
        r".*archive-api\.open-meteo\.com.*", {"status": 200, "body": body}
    )
    contract.settle_policy(pid)
    _source_rejected_fails_closed(contract, direct_vm, pid)


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
    # settle-eligible: end 2030-01-06 + 1 day + 1h = 2030-01-07T01:00:00Z
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
