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
