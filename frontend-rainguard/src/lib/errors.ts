/**
 * Consensus reads are slow and occasionally dropped by the RPC (a read needs
 * every validator to answer). Retrying transient network failures keeps the
 * UI from flashing errors on a hiccup; real contract errors surface as-is.
 */

const RETRY_MS = 1200;
const MAX_RETRIES = 4;

function isRetryable(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  return (
    msg.includes("Failed to fetch") ||
    msg.includes("fetch failed") ||
    msg.includes("ECONNRESET") ||
    msg.includes("ETIMEDOUT") ||
    msg.includes("socket hang up") ||
    msg.includes("network") ||
    msg.includes("timeout")
  );
}

/** Run a consensus read, retrying transient network failures. */
export async function withReadRetry<T>(fn: () => Promise<T>): Promise<T> {
  let lastErr: unknown;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastErr = err;
      if (!isRetryable(err) || attempt === MAX_RETRIES) break;
      await new Promise((r) => setTimeout(r, RETRY_MS * (attempt + 1)));
    }
  }
  throw lastErr;
}

/**
 * The revert reasons RainGuard raises. Surfacing the contract's own words is
 * the clearest possible error for a user; anything else stays generic.
 */
const KNOWN_REVERTS: Array<[RegExp, string]> = [
  [/coverage has already begun/, "Buying closed when the coverage window opened. Coverage can only be bought before it begins; the insurer can still cancel this policy."],
  [/coverage must not have begun yet/, "The window has already started, so this coverage can't be created. A policy is only issued before its window opens."],
  [/coverage window has not ended yet/, "The coverage window is still running. Settlement opens after the window ends."],
  [/policy is not active/, "This policy is not active, so it cannot be settled or closed."],
  [/policy is not open for purchase/, "This policy is no longer open for purchase (already bought or cancelled)."],
  [/policy is not stale yet/, "This policy is not stale yet. It can only be unwound after the stale window passes."],
  [/settlement retries not exhausted/, "This policy hasn't exhausted its settlement retries yet. Stale closure only opens after recorded failed attempts hit the limit."],
  [/settlement retry limit reached/, "Settlement retries ran out. Close the policy as stale to refund both sides."],
  [/settlement was just attempted/, "Settlement was just attempted. Wait a few minutes before retrying."],
  [/exact payout must be sent/, "Send exactly the payout amount to fund the escrow."],
  [/exact premium must be sent/, "Send exactly the premium amount shown on the policy."],
  [/payout must be greater than zero/, "The payout must be greater than zero."],
  [/premium must be greater than zero/, "The premium must be greater than zero."],
  [/payout must be 1000 GEN or less/, "The payout must be 1000 GEN or less."],
  [/premium must be 1000 GEN or less/, "The premium must be 1000 GEN or less."],
  [/insurer cannot buy their own policy/, "The insurer cannot buy their own policy."],
  [/only the insurer can cancel/, "Only the insurer who funded this policy can cancel it."],
  [/only an open policy can be cancelled/, "Only an open policy can be cancelled; this one is already taken or settled."],
  [/end_date must not be before start_date/, "The end date must not be before the start date."],
  [/window must be \d+ days or less/, "The coverage window is capped at 31 days."],
  [/metric must be rainfall or temperature/, "Pick rainfall or temperature as the metric."],
  [/threshold must be a positive decimal/, "The threshold must be a positive number."],
  [/condition must be below or above/, "The trigger must be 'below' or 'above'."],
  [/lat must be a decimal/, "Latitude must be a decimal between -90 and 90."],
  [/lon must be a decimal/, "Longitude must be a decimal between -180 and 180."],
  [/dates must be YYYY-MM-DD/, "Dates must use the YYYY-MM-DD format."],
  [/policy not found/, "That policy does not exist on-chain."],
];

/** Strip viem's version banner and whitespace noise from a raw message. */
function cleanRaw(raw: string): string {
  return raw
    .replace(/Version: viem@[0-9.]+/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Map a thrown error to a short, human sentence the UI can show.
 *
 * Contract reverts become the contract's own reason; wallet rejections and
 * network failures get their own wording; anything unknown collapses to a
 * stable generic message instead of leaking a viem stack trace.
 */
export function describeError(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err ?? "");
  const code = (err as { code?: unknown } | null)?.code;

  // MetaMask rejects with code 4001 when the user clicks "reject".
  if (code === 4001) return "The transaction was cancelled in your wallet.";
  // The chain is unreachable or the RPC dropped the request mid-flight.
  if (/failed to fetch|fetch failed|econnreset|etimedout|socket hang up|network error|connection/i.test(raw)) {
    return "Can't reach the GenLayer network. Check your connection and try again.";
  }

  for (const [re, message] of KNOWN_REVERTS) {
    if (re.test(raw)) return message;
  }

  const cleaned = cleanRaw(raw);
  if (!cleaned || cleaned.length < 4) return "Something went wrong. Try again.";
  // The raw error is usually a wall of JSON. Cut it to the first useful
  // fragment so the user sees a reason, not a stack trace.
  return cleaned.length > 160 ? `${cleaned.slice(0, 157)}…` : cleaned;
}
