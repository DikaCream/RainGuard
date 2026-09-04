# RainGuard

Parametric weather insurance on GenLayer. An insurer funds a payout against a measurable trigger, a buyer pays a premium for the coverage, and when the covered window closes the validators read the Open-Meteo archive for that exact place and dates. Trigger hit, buyer is paid. Trigger missed, insurer keeps the pot. Nobody files a claim and nobody argues.

Live: `https://rainguard.vercel.app` (pending) — contract `0x1b296C21d6362bDb92A4ec6b0F1664bc4C173Cd9` on StudioNet.

## What it covers

Two trigger types, each with two directions:

- **Rainfall**, summed across the window (mm): below the threshold is drought cover, above is flood cover.
- **Temperature**, max daily value across the window (°C): below is a cold snap, above is a heatwave.

A policy pins a location (lat/lon), a start and end date, a threshold and a direction. Insurers create coverage and lock the payout as escrow. Buyers take coverage while the window is still running by paying the premium. Buying closes the moment the window ends, because after that the outcome is already knowable from public data and a stale policy could never be bought and settled instantly.

## Why the settlement is boring on purpose

The trigger is arithmetic on published weather history. Two leader validators fetch the same archive URL, sum the same numbers, and must return byte-identical output under the strict equivalence principle. No LLM reads a prompt, no prose, nothing subjective. If the archive can't be fetched or parsed, the policy fails closed, stays ACTIVE and can be retried. If consensus never settles within a week of eligibility, anyone can unwind it: the premium goes back to the buyer, the payout back to the insurer. A network failure profits nobody.

Windows are capped at 31 days (Open-Meteo's archive limit) and payouts at 1000 GEN. Escrow is tracked as a running total and asserted to equal the sum of held funds after every state change.

## Repository layout

```
contracts/rain_guard.py          the contract
frontend-rainguard/              Vite + React app (create, browse, buy, settle)
tests/direct/test_rain_guard.py  fast VM tests, mocked weather
tests/integration/test_rain_guard.py  on-chain tests, real consensus
tests/seed_rainguard_live.py     deploy + seed live demo policies
gltest.config.yaml               StudioNet accounts (test-only)
```

## Running the tests

The direct suite needs the gltest venv and nothing else:

```bash
pip install -r requirements.txt
pytest tests/direct/ -q          # 133 tests
genvm-lint check contracts/rain_guard.py
```

The integration suite needs the StudioNet RPC (accounts configured in `gltest.config.yaml`):

```bash
gltest --network studionet tests/integration/test_rain_guard.py -v -s
```

To redeploy and reseed the live board:

```bash
gltest --network studionet tests/seed_rainguard_live.py -v -s
```

Copy the printed address into `frontend-rainguard/src/config.ts` or the Vercel env var `VITE_CONTRACT_ADDRESS`, then rebuild.

## The frontend

A Vite + React SPA. Connect any injected wallet (MetaMask with the StudioNet chain, which the app adds on demand), browse coverage, buy with the premium shown, issue your own policy, and settle policies whose window has ended. Wallet balance comes from the provider; every read against consensus retries transient network failures instead of flashing an error. StudioNet is gasless, so issuing only needs the payout amount in your wallet.

## Data source

[Open-Meteo Archive API](https://open-meteo.com/) (free, no key). The contract requests both daily metrics in one call and only ever reads `time`, `precipitation_sum` and `temperature_2m_max`.

## Known limits

- Settlement needs the covered window to end before it runs, so a fresh deploy shows ACTIVE policies that settle over the next day or two. That is a design decision, not a bug: the alternative is letting people buy coverage for a window that already finished.
- One insurer per policy. A policy is covered by a single buyer; there's no fractional syndication yet.
