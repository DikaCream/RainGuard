# RainGuard

Parametric weather insurance on GenLayer. An insurer funds a payout against a measurable trigger, a buyer pays a premium for the coverage, and when the covered window closes the validators read the Open-Meteo archive for that exact place and those dates. Trigger hits, the buyer is paid. It misses, the insurer keeps the pot. Nobody files a claim and nobody argues.

Live at `https://rainguard-eight.vercel.app`. Contract `0xEaf759D40412D1445b54d712c94cde16c60E36ee` on StudioNet.

## What it covers

Two triggers, two directions each.

- Rainfall, summed across the window in mm. Below the threshold is drought cover; above it is flood cover.
- Temperature, max daily value across the window in °C. Below is a cold snap, above is a heatwave.

A policy pins a location (lat/lon), a start and end date, a threshold, and a direction. The insurer creates the coverage and locks the payout as escrow. Buyers take coverage while the window is still running by paying the premium. Buying closes the moment the window ends, because from that point the outcome is knowable from public data, and a stale policy that could be bought and settled instantly is exactly the hole this closes.

## Why settlement is boring on purpose

The trigger is arithmetic on published weather history. Two leader validators fetch the same archive URL, compute the same numbers, and have to return byte-identical output under the strict equivalence principle. No LLM reads a prompt. No prose. Nothing subjective.

If the archive can't be fetched or parsed, the policy fails closed: it stays ACTIVE and can be retried. If consensus never settles within a week of eligibility, anyone can unwind it, with the premium going back to the buyer and the payout back to the insurer. A network failure profits nobody.

Windows are capped at 31 days (Open-Meteo's archive limit) and payouts at 1000 GEN. Escrow is tracked as a running total and asserted to equal the sum of held funds after every state change.

## Repository layout

```
contracts/rain_guard.py              the contract
frontend-rainguard/                  Vite + React app (create, browse, buy, settle)
tests/direct/test_rain_guard.py      fast VM tests, mocked weather
tests/integration/test_rain_guard.py on-chain tests, real consensus
tests/deploy_reseed_rainguard.py     deploy a fresh copy + seed live demo policies
```

## Running the tests

The direct suite needs only the gltest venv:

```bash
pip install -r requirements.txt
pytest tests/direct/test_rain_guard.py -q   # 32 tests
genvm-lint check contracts/rain_guard.py
```

The integration suite needs the StudioNet RPC and funded accounts. `gltest.config.yaml` is gitignored; create one locally with your own StudioNet keys:

```yaml
networks:
  studionet:
    accounts:
      - "<your private key>"
```

```bash
gltest --network studionet tests/integration/test_rain_guard.py -v -s
```

To redeploy a fresh copy and reseed the live board:

```bash
gltest --network studionet tests/deploy_reseed_rainguard.py -v -s
```

Copy the printed address into `frontend-rainguard/src/config.ts`, or set the Vercel env var `VITE_CONTRACT_ADDRESS`, then rebuild.

## The frontend

A Vite + React SPA. Connect any injected wallet (MetaMask with the StudioNet chain, which the app adds on demand), browse coverage, buy with the premium shown, issue your own policy, and settle policies whose window has ended. Wallet balance comes from the provider. Reads against consensus retry transient network failures instead of flashing an error, and StudioNet is gasless, so issuing only needs the payout amount in your wallet.

## Data source

[Open-Meteo Archive API](https://open-meteo.com/), free and keyless. The contract requests both daily metrics in one call and only ever reads `time`, `precipitation_sum`, and `temperature_2m_max`.

## Known limits

- Settlement needs the covered window to end before it runs, so a fresh deploy shows ACTIVE policies that settle over the next day or two. That's a design decision, not a bug: the alternative is letting people buy coverage for a window that already finished.
- One insurer and one buyer per policy. No fractional syndication yet.
