# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
RainGuard — parametric weather insurance that settles itself.

A policy covers a location over a date window against a measurable trigger:
rainfall below a threshold (drought), rainfall above it (flood), temperature
above a threshold (heatwave) or below one (cold snap). The insurer creates the
policy and locks the payout in escrow; a buyer pays the premium to take the
coverage. After the window ends, anyone triggers settlement and GenLayer's
validators fetch the Open-Meteo archive for the exact location and dates, so
the money moves on published weather data, not on a filed claim.

The settlement is deliberately NOT an AI judgment. The trigger is a number
(past rainfall sum, past max temperature) that any validator can read from the
same public archive. Both leaders fetch the same URL and compute the same
value, so consensus uses the strict equivalence principle: outputs must match
byte-for-byte. There is no prompt, no prose, and nothing subjective to argue
about.

ESCROW INVARIANT (must hold after every method, on every path):
    escrow_locked == sum over every policy in {OPEN, ACTIVE} of held funds,
    where OPEN holds `payout` and ACTIVE holds `payout + premium`.
It is tracked incrementally (+payout on create, +premium on buy, -payout on
cancel, -(payout+premium) on settle/stale-close) and never recomputed by
looping.

State machine: OPEN -> ACTIVE -> PAID | EXPIRED | CANCELLED | REFUNDED.

Buying closes when the coverage window closes: once the window is over, the
outcome is already knowable from public weather data, so a stale OPEN policy
can never be bought and immediately settled. An insurer whose policy finds no
buyer before the window ends can only cancel and recover the payout.
"""
from genlayer import *
from dataclasses import dataclass
import datetime
import json
import re
import typing

# ---------------------------------------------------------------- statuses
OPEN = "OPEN"  # insurer funded the payout; waiting for a buyer
ACTIVE = "ACTIVE"  # a buyer paid the premium; coverage is live
PAID = "PAID"  # trigger hit; buyer received payout + premium back
EXPIRED = "EXPIRED"  # trigger missed; insurer received payout + premium
CANCELLED = "CANCELLED"  # insurer backed out before any buyer; payout returned
REFUNDED = "REFUNDED"  # consensus never settled; both sides unwound

RAINFALL = "rainfall"
TEMPERATURE = "temperature"
METRICS = (RAINFALL, TEMPERATURE)
BELOW = "below"
ABOVE = "above"
CONDITIONS = (BELOW, ABOVE)

SECONDS_PER_DAY = 86400
# Settlement reads a completed window, so it starts the day AFTER the window's
# end date, plus this buffer for the archive to publish the final daily value.
SETTLE_AFTER_END_SECONDS = 3600
# A failed settlement (fetch/parse error, validator disagreement) keeps the
# policy ACTIVE; re-runs are throttled and capped like any consensus step.
SETTLE_COOLDOWN_SECONDS = 300
MAX_SETTLE_ATTEMPTS = 5
# If consensus can never settle, anyone may close the policy after this long
# past its settle-eligible time: buyer gets the premium back, insurer gets the
# payout back. Nobody profits from a network failure.
STALE_AFTER_SETTLE_SECONDS = 7 * SECONDS_PER_DAY

# Input bounds.
GEN_ONE = 10**18
MAX_PAYOUT_GEN = 1000
MAX_WINDOW_DAYS = 31  # Open-Meteo archive caps daily requests at ~92 days
MAX_COORD_CHARS = 16
MAX_THRESHOLD_CHARS = 20

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DECIMAL_RE = re.compile(r"^[+-]?\d+(\.\d+)?$")


def _is_date(s: str) -> bool:
    if not _DATE_RE.match(s):
        return False
    try:
        datetime.date.fromisoformat(s)
        return True
    except ValueError:
        return False


def _is_decimal(s: str, max_len: int, min_value: float, max_value: float) -> bool:
    if not (0 < len(s) <= max_len) or not _DECIMAL_RE.match(s):
        return False
    try:
        v = float(s)
    except ValueError:
        return False
    return min_value <= v <= max_value


def _strip_control_chars(text: str) -> str:
    """Drop C0/C1 control characters (except tab/newline) from stored text."""
    return "".join(
        ch for ch in text if ch in ("\t", "\n") or (ord(ch) >= 32 and ord(ch) != 127)
    )


# ---------------------------------------------------------------- payouts
@gl.evm.contract_interface
class _NativeRecipient:
    """A plain address we send native GEN to — a wallet.

    The EVM interface emits an EthSend with empty calldata, which is the
    native-value transfer an ordinary address can receive.
    """

    class View:
        pass

    class Write:
        pass


# ---------------------------------------------------------------- storage
@allow_storage
@dataclass
class Policy:
    id: u256
    insurer: Address  # created the policy, locked the payout
    buyer: Address  # zero unless bought
    bought: bool  # a buyer has paid the premium
    metric: str  # rainfall | temperature
    lat: str  # decimal string, validated
    lon: str
    start_date: str  # ISO YYYY-MM-DD
    end_date: str
    threshold: str  # decimal string (mm for rainfall, degC for temperature)
    condition: str  # below | above
    premium: u256
    payout: u256
    status: str  # OPEN | ACTIVE | PAID | EXPIRED | CANCELLED | REFUNDED
    measured: str  # the value validators computed, once settled
    attempts: u8
    last_settled_at: u256
    created_at: u256
    bought_at: u256


# ---------------------------------------------------------------- events
class PolicyCreated(gl.Event):
    def __init__(self, policy_id: u256, /, **blob): ...


class PolicyBought(gl.Event):
    def __init__(self, policy_id: u256, /, **blob): ...


class PolicyCancelled(gl.Event):
    def __init__(self, policy_id: u256, /, **blob): ...


class PolicySettled(gl.Event):
    def __init__(self, policy_id: u256, /, **blob): ...


class SettlementFailed(gl.Event):
    """Settlement produced unusable output — policy stays ACTIVE for a retry."""

    def __init__(self, policy_id: u256, /): ...


class PolicyClosedStale(gl.Event):
    """Consensus never settled — premium to buyer, payout to insurer."""

    def __init__(self, policy_id: u256, /, **blob): ...


# ---------------------------------------------------------------- contract
class RainGuard(gl.Contract):
    policies: TreeMap[u256, Policy]
    all_policies: DynArray[u256]
    insurer_policies: TreeMap[Address, DynArray[u256]]
    buyer_policies: TreeMap[Address, DynArray[u256]]
    next_policy_id: u256
    escrow_locked: u256  # total GEN held in {OPEN, ACTIVE} policies

    def __init__(self):
        self.next_policy_id = u256(1)
        self.escrow_locked = u256(0)

    # ------------------------------------------------------------ helpers
    def _now(self) -> int:
        raw = gl.message_raw.get("datetime")
        if not raw:
            raise gl.vm.UserError("no timestamp available in this message")
        try:
            return int(
                datetime.datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
            )
        except (ValueError, TypeError):
            raise gl.vm.UserError("malformed timestamp in this message")

    def _policy_or_revert(self, pid: int) -> Policy:
        p = self.policies.get(u256(pid))
        if p is None:
            raise gl.vm.UserError("policy not found")
        return p

    def _date_to_ts(self, date_str: str) -> int:
        """Midnight UTC of the given YYYY-MM-DD date."""
        return int(
            datetime.datetime.fromisoformat(date_str + "T00:00:00+00:00").timestamp()
        )

    def _settle_eligible_at(self, p: Policy) -> int:
        # The window covers start_date..end_date inclusive, so the last day is
        # complete at the start of the day after end_date.
        return self._date_to_ts(p.end_date) + SECONDS_PER_DAY + SETTLE_AFTER_END_SECONDS

    # ------------------------------------------------------------ policies
    @gl.public.write.payable
    def create_policy(
        self,
        metric: str,
        lat: str,
        lon: str,
        start_date: str,
        end_date: str,
        threshold: str,
        condition: str,
        premium: u256,
        payout: u256,
    ) -> u256:
        """Insurer creates coverage and locks the payout as escrow."""
        insurer = gl.message.sender_address
        value = int(gl.message.value)
        payout_int = int(payout)
        if value != payout_int:
            raise gl.vm.UserError("exact payout must be sent")
        if payout_int <= 0:
            raise gl.vm.UserError("payout must be greater than zero")
        if payout_int > MAX_PAYOUT_GEN * GEN_ONE:
            raise gl.vm.UserError("payout must be 1000 GEN or less")
        premium_int = int(premium)
        if premium_int <= 0:
            raise gl.vm.UserError("premium must be greater than zero")
        if premium_int > MAX_PAYOUT_GEN * GEN_ONE:
            raise gl.vm.UserError("premium must be 1000 GEN or less")

        metric = _strip_control_chars(metric).strip().lower()
        if metric not in METRICS:
            raise gl.vm.UserError("metric must be rainfall or temperature")
        lat = _strip_control_chars(lat).strip()
        lon = _strip_control_chars(lon).strip()
        if not _is_decimal(lat, MAX_COORD_CHARS, -90.0, 90.0):
            raise gl.vm.UserError("lat must be a decimal between -90 and 90")
        if not _is_decimal(lon, MAX_COORD_CHARS, -180.0, 180.0):
            raise gl.vm.UserError("lon must be a decimal between -180 and 180")
        start_date = _strip_control_chars(start_date).strip()
        end_date = _strip_control_chars(end_date).strip()
        if not _is_date(start_date) or not _is_date(end_date):
            raise gl.vm.UserError("dates must be YYYY-MM-DD")
        start_ts = self._date_to_ts(start_date)
        end_ts = self._date_to_ts(end_date)
        if end_ts < start_ts:
            raise gl.vm.UserError("end_date must not be before start_date")
        if end_ts - start_ts > (MAX_WINDOW_DAYS - 1) * SECONDS_PER_DAY:
            raise gl.vm.UserError(f"window must be {MAX_WINDOW_DAYS} days or less")
        # The window must still be live or upcoming: a fully-ended window can
        # never be bought (see buy_policy), so it would be dead on arrival.
        if self._date_to_ts(end_date) + SECONDS_PER_DAY < self._now():
            raise gl.vm.UserError("end_date must be today or later")
        threshold = _strip_control_chars(threshold).strip()
        if not _is_decimal(threshold, MAX_THRESHOLD_CHARS, 0.0, 100000.0):
            raise gl.vm.UserError("threshold must be a positive decimal")
        condition = _strip_control_chars(condition).strip().lower()
        if condition not in CONDITIONS:
            raise gl.vm.UserError("condition must be below or above")

        pid = int(self.next_policy_id)
        self.next_policy_id = u256(pid + 1)
        self.policies[u256(pid)] = Policy(
            id=u256(pid),
            insurer=insurer,
            buyer=insurer,
            bought=False,
            metric=metric,
            lat=lat,
            lon=lon,
            start_date=start_date,
            end_date=end_date,
            threshold=threshold,
            condition=condition,
            premium=u256(premium_int),
            payout=u256(payout_int),
            status=OPEN,
            measured="",
            attempts=u8(0),
            last_settled_at=u256(0),
            created_at=u256(self._now()),
            bought_at=u256(0),
        )
        self.all_policies.append(u256(pid))
        self.insurer_policies.get_or_insert_default(insurer).append(u256(pid))
        self.escrow_locked = u256(int(self.escrow_locked) + payout_int)
        PolicyCreated(
            u256(pid),
            metric=metric,
            start_date=start_date,
            end_date=end_date,
            premium=premium_int,
            payout=payout_int,
        ).emit()
        return u256(pid)

    @gl.public.write.payable
    def buy_policy(self, policy_id: u256) -> None:
        """Buyer pays the premium and takes the coverage."""
        p = self._policy_or_revert(int(policy_id))
        if p.status != OPEN:
            raise gl.vm.UserError("policy is not open for purchase")
        now = self._now()
        # Buying is allowed through the last day of the coverage window and no
        # later: once the window is over, the outcome is already knowable, so
        # a stale OPEN policy can never be bought and immediately settled.
        # The insurer's only way out then is cancel_policy.
        if now >= self._date_to_ts(p.end_date) + SECONDS_PER_DAY:
            raise gl.vm.UserError(
                "coverage window has ended — a policy can no longer be bought"
            )
        buyer = gl.message.sender_address
        if p.insurer == buyer:
            raise gl.vm.UserError("the insurer cannot buy their own policy")
        premium_int = int(p.premium)
        if int(gl.message.value) != premium_int:
            raise gl.vm.UserError("exact premium must be sent")
        p.buyer = buyer
        p.bought = True
        p.bought_at = u256(now)
        p.status = ACTIVE
        self.buyer_policies.get_or_insert_default(buyer).append(u256(int(policy_id)))
        self.escrow_locked = u256(int(self.escrow_locked) + premium_int)
        PolicyBought(u256(int(policy_id)), buyer=buyer.as_hex, premium=premium_int).emit()

    @gl.public.write
    def cancel_policy(self, policy_id: u256) -> None:
        """Insurer backs out while the policy is still OPEN; payout returned.

        Also the escape hatch when the window ends with no buyer: an OPEN
        policy can never settle, so the insurer must be able to recover.
        """
        p = self._policy_or_revert(int(policy_id))
        if p.status != OPEN:
            raise gl.vm.UserError("only an open policy can be cancelled")
        if p.insurer != gl.message.sender_address:
            raise gl.vm.UserError("only the insurer can cancel the policy")
        amount = int(p.payout)
        # Checks-effects-interactions: all state BEFORE the transfer.
        p.status = CANCELLED
        self.escrow_locked = u256(int(self.escrow_locked) - amount)
        _NativeRecipient(p.insurer).emit_transfer(value=u256(amount))
        PolicyCancelled(u256(int(policy_id)), payout=amount).emit()

    # ------------------------------------------------------------ settlement
    @gl.public.write
    def settle_policy(self, policy_id: u256) -> None:
        """Run validator consensus on the weather trigger. Permissionless.

        Both leader validators fetch the Open-Meteo archive for the policy's
        location and window, compute the same number, and must agree
        byte-for-byte (strict equivalence) before any money moves.
        """
        p = self._policy_or_revert(int(policy_id))
        if p.status != ACTIVE:
            raise gl.vm.UserError("policy is not active")
        now = self._now()
        if now < self._settle_eligible_at(p):
            raise gl.vm.UserError("coverage window has not ended yet")
        if int(p.attempts) >= MAX_SETTLE_ATTEMPTS:
            raise gl.vm.UserError(
                "settlement retry limit reached — close the policy stale to unwind both sides"
            )
        if (
            int(p.last_settled_at) != 0
            and now < int(p.last_settled_at) + SETTLE_COOLDOWN_SECONDS
        ):
            raise gl.vm.UserError("settlement was just attempted — wait before retrying")
        self._run_settlement(int(policy_id))

    @gl.public.write
    def close_stale_policy(self, policy_id: u256) -> None:
        """Unwind a policy consensus can never settle — both sides refunded.

        An ACTIVE policy pins its escrow forever if consensus never produced
        a settlement and retries are exhausted. After the stale window anyone
        may close it: the buyer gets the premium back, the insurer gets the
        payout back. The network failed to settle, so nobody profits.
        """
        p = self._policy_or_revert(int(policy_id))
        if p.status != ACTIVE:
            raise gl.vm.UserError("policy is not active")
        if self._now() < self._settle_eligible_at(p) + STALE_AFTER_SETTLE_SECONDS:
            raise gl.vm.UserError("policy is not stale yet")
        p.status = REFUNDED
        amount = int(p.payout) + int(p.premium)
        # Checks-effects-interactions: all state BEFORE any transfer.
        self.escrow_locked = u256(int(self.escrow_locked) - amount)
        _NativeRecipient(p.buyer).emit_transfer(value=u256(int(p.premium)))
        _NativeRecipient(p.insurer).emit_transfer(value=u256(int(p.payout)))
        PolicyClosedStale(
            u256(int(policy_id)), premium=int(p.premium), payout=int(p.payout)
        ).emit()

    # ------------------------------------------------------------ internal
    def _build_archive_url(self, p: Policy) -> str:
        """Open-Meteo archive API URL for the policy's window and metrics.

        Both metrics are requested in one call so a single fetch covers
        rainfall and temperature policies. The response is a plain JSON
        document; validators parse it as text and compute the trigger.
        """
        return (
            "https://archive-api.open-meteo.com/v1/archive"
            f"?latitude={p.lat}&longitude={p.lon}"
            f"&start_date={p.start_date}&end_date={p.end_date}"
            "&daily=precipitation_sum,temperature_2m_max&timezone=UTC"
        )

    def _run_settlement(self, policy_id: int) -> None:
        """Fetch the archive, compute the trigger, and move the money.

        Fail closed: unusable output leaves the policy ACTIVE and emits
        SettlementFailed; it never pays out on a guess.
        """
        p = self._policy_or_revert(policy_id)
        p.attempts = u8(min(int(p.attempts) + 1, 255))
        p.last_settled_at = u256(self._now())
        metric = p.metric
        condition = p.condition
        threshold = float(p.threshold)
        url = self._build_archive_url(p)

        def do_settle() -> str:
            try:
                text = gl.nondet.web.render(url, mode="text")
                data = json.loads(text)
                daily = data.get("daily") or {}
                time_rows = daily.get("time") or []
                if metric == RAINFALL:
                    raw = daily.get("precipitation_sum") or []
                else:
                    raw = daily.get("temperature_2m_max") or []
                if not time_rows or len(raw) < len(time_rows):
                    return json.dumps({"error": "incomplete weather data"})
                values = [
                    float(v) for v in raw[: len(time_rows)] if v is not None
                ]
                if len(values) < len(time_rows):
                    return json.dumps({"error": "incomplete weather data"})
                measured = sum(values) if metric == RAINFALL else max(values)
                triggered = (
                    measured < threshold if condition == BELOW else measured > threshold
                )
                return json.dumps(
                    {
                        "triggered": triggered,
                        "measured": round(measured, 2),
                    },
                    sort_keys=True,
                )
            except Exception:
                # Leader could not fetch or parse — explicit sentinel so the
                # deterministic half fails CLOSED.
                return json.dumps({"error": "unusable weather data"})

        # Strict equivalence: both leaders must return byte-identical JSON.
        settle_ok = False
        triggered = False
        measured = ""
        try:
            result_raw = gl.eq_principle.strict_eq(do_settle)
            result = json.loads(result_raw)
            if "error" not in result:
                measured = str(result["measured"])
                triggered = bool(result["triggered"])
                settle_ok = True
        except Exception:
            settle_ok = False
        if not settle_ok:
            SettlementFailed(u256(policy_id)).emit()
            return

        p.measured = measured
        amount = int(p.payout) + int(p.premium)
        # Checks-effects-interactions: all state BEFORE any transfer.
        self.escrow_locked = u256(int(self.escrow_locked) - amount)
        if triggered:
            p.status = PAID
            _NativeRecipient(p.buyer).emit_transfer(value=u256(amount))
            PolicySettled(
                u256(policy_id),
                outcome="PAID",
                measured=measured,
                trigger="hit",
                recipient=p.buyer.as_hex,
                amount=amount,
            ).emit()
            return
        p.status = EXPIRED
        _NativeRecipient(p.insurer).emit_transfer(value=u256(amount))
        PolicySettled(
            u256(policy_id),
            outcome="EXPIRED",
            measured=measured,
            trigger="missed",
            recipient=p.insurer.as_hex,
            amount=amount,
        ).emit()

    # ------------------------------------------------------------ views
    @gl.public.view
    def get_config(self) -> dict[str, typing.Any]:
        return {
            "policy_count": int(self.next_policy_id) - 1,
            "escrow_locked": int(self.escrow_locked),
            "metrics": list(METRICS),
            "conditions": list(CONDITIONS),
            "max_window_days": MAX_WINDOW_DAYS,
            "max_payout_gen": MAX_PAYOUT_GEN,
            "settle_after_end_seconds": SETTLE_AFTER_END_SECONDS,
            "max_settle_attempts": MAX_SETTLE_ATTEMPTS,
        }

    @gl.public.view
    def get_stats(self) -> dict[str, typing.Any]:
        total = int(self.next_policy_id) - 1
        counts = {s: 0 for s in (OPEN, ACTIVE, PAID, EXPIRED, CANCELLED, REFUNDED)}
        for pid in self.all_policies:
            p = self.policies.get(pid)
            if p is not None:
                counts[p.status] += 1
        return {
            "total_policies": total,
            "open": counts[OPEN],
            "active": counts[ACTIVE],
            "paid": counts[PAID],
            "expired": counts[EXPIRED],
            "cancelled": counts[CANCELLED],
            "refunded": counts[REFUNDED],
            "escrow_locked": int(self.escrow_locked),
        }

    @gl.public.view
    def get_policy(self, policy_id: u256) -> typing.Any:
        p = self.policies.get(u256(int(policy_id)))
        if p is None:
            return None
        return self._policy_dict(p)

    @gl.public.view
    def list_policies(self, offset: u256, limit: u256) -> list[typing.Any]:
        """Page over ALL policies (ids ascend, newest last)."""
        lim = min(int(limit), 50)
        out: list[typing.Any] = []
        n = len(self.all_policies)
        for i in range(int(offset), min(int(offset) + lim, n)):
            p = self.policies.get(self.all_policies[i])
            if p is not None:
                out.append(self._policy_dict(p))
        return out

    @gl.public.view
    def list_insurer_policies(
        self, insurer: Address, offset: u256, limit: u256
    ) -> list[typing.Any]:
        return self._page_policies(
            self.insurer_policies.get(insurer), int(offset), int(limit)
        )

    @gl.public.view
    def list_buyer_policies(
        self, buyer: Address, offset: u256, limit: u256
    ) -> list[typing.Any]:
        return self._page_policies(
            self.buyer_policies.get(buyer), int(offset), int(limit)
        )

    def _page_policies(
        self, ids: typing.Any, offset: int, limit: int
    ) -> list[typing.Any]:
        if ids is None:
            return []
        lim = min(limit, 50)
        out: list[typing.Any] = []
        n = len(ids)
        for i in range(offset, min(offset + lim, n)):
            p = self.policies.get(ids[i])
            if p is not None:
                out.append(self._policy_dict(p))
        return out

    def _policy_dict(self, p: Policy) -> dict[str, typing.Any]:
        return {
            "id": int(p.id),
            "insurer": p.insurer.as_hex,
            "buyer": p.buyer.as_hex if p.bought else "",
            "metric": p.metric,
            "lat": p.lat,
            "lon": p.lon,
            "start_date": p.start_date,
            "end_date": p.end_date,
            "threshold": p.threshold,
            "condition": p.condition,
            "premium": int(p.premium),
            "payout": int(p.payout),
            "status": p.status,
            "measured": p.measured,
            "attempts": int(p.attempts),
            "last_settled_at": int(p.last_settled_at),
            "created_at": int(p.created_at),
            "bought_at": int(p.bought_at),
            "settle_eligible_at": self._settle_eligible_at(p),
            "stale_at": self._settle_eligible_at(p) + STALE_AFTER_SETTLE_SECONDS,
        }