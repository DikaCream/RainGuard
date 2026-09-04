import { useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useRainGuard } from "../context/RainGuardContext";
import { describeError } from "../lib/errors";
import { parseGen } from "../lib/client";
import { MAX_PAYOUT_GEN, MAX_WINDOW_DAYS } from "../config";
import { DropletIcon, ThermometerIcon, ShieldIcon, BoltIcon } from "../components/icons";

interface FieldErrors {
  metric?: string;
  coords?: string;
  dates?: string;
  threshold?: string;
  premium?: string;
  payout?: string;
}

// A few real city coordinates so the form is usable without a map.
const PRESETS: { label: string; lat: string; lon: string }[] = [
  { label: "Jakarta", lat: "-6.2", lon: "106.8" },
  { label: "Singapore", lat: "1.35", lon: "103.82" },
  { label: "Tokyo", lat: "35.68", lon: "139.69" },
  { label: "London", lat: "51.51", lon: "-0.13" },
  { label: "São Paulo", lat: "-23.55", lon: "-46.63" },
];

function todayISO(): string {
  const d = new Date();
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10);
}

function addDaysISO(iso: string, days: number): string {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export default function Create() {
  const { wallet, contract } = useRainGuard();
  const navigate = useNavigate();

  const [metric, setMetric] = useState<"rainfall" | "temperature">("rainfall");
  const [city, setCity] = useState(""); // preset label, or custom coords
  const [lat, setLat] = useState("-6.2");
  const [lon, setLon] = useState("106.8");
  const [startDate, setStartDate] = useState(todayISO());
  const [endDate, setEndDate] = useState(addDaysISO(todayISO(), 7));
  const [threshold, setThreshold] = useState("");
  const [condition, setCondition] = useState<"below" | "above">("below");
  const [premium, setPremium] = useState("");
  const [payout, setPayout] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const units = metric === "rainfall" ? "mm" : "°C";
  const thresholdPlaceholder = metric === "rainfall" ? "e.g. 30" : "e.g. 35";

  const humanTrigger = useMemo(() => {
    if (!threshold) return "";
    const dir = condition === "below" ? "below" : "above";
    const what =
      metric === "rainfall"
        ? condition === "below"
          ? "drier than"
          : "wetter than"
        : condition === "below"
          ? "cooler than"
          : "hotter than";
    return `${metric} ${dir} ${threshold}${units} (${what})`;
  }, [metric, condition, threshold, units]);

  function pickPreset(label: string) {
    const p = PRESETS.find((x) => x.label === label);
    if (!p) return;
    setCity(label);
    setLat(p.lat);
    setLon(p.lon);
  }

  const validate = (): FieldErrors => {
    const errors: FieldErrors = {};
    const latN = Number(lat);
    const lonN = Number(lon);
    if (!/^[+-]?\d+(\.\d+)?$/.test(lat.trim()) || latN < -90 || latN > 90) {
      errors.coords = "Latitude must be between -90 and 90.";
    }
    if (!/^[+-]?\d+(\.\d+)?$/.test(lon.trim()) || lonN < -180 || lonN > 180) {
      errors.coords = "Longitude must be between -180 and 180.";
    }
    if (!startDate || !endDate) {
      errors.dates = "Pick a start and end date.";
    } else {
      const s = new Date(startDate + "T00:00:00Z").getTime();
      const e = new Date(endDate + "T00:00:00Z").getTime();
      const today = new Date(todayISO() + "T00:00:00Z").getTime();
      if (e < s) errors.dates = "End date must not be before start date.";
      else if (e - s > (MAX_WINDOW_DAYS - 1) * 86400000)
        errors.dates = `Window must be ${MAX_WINDOW_DAYS} days or less.`;
      else if (e + 86400000 < today)
        errors.dates = "The window must end today or later.";
    }
    const t = Number(threshold);
    if (!threshold.trim() || !isFinite(t) || t <= 0) {
      errors.threshold = "Threshold must be a positive number.";
    }
    try {
      const p = parseGen(premium);
      if (p <= 0n) errors.premium = "Premium must be greater than zero.";
      if (p > BigInt(MAX_PAYOUT_GEN) * 10n ** 18n)
        errors.premium = `Premium must be ${MAX_PAYOUT_GEN} GEN or less.`;
    } catch {
      errors.premium = "Enter a valid GEN amount (e.g. 0.5 or 2).";
    }
    try {
      const o = parseGen(payout);
      if (o <= 0n) errors.payout = "Payout must be greater than zero.";
      if (o > BigInt(MAX_PAYOUT_GEN) * 10n ** 18n)
        errors.payout = `Payout must be ${MAX_PAYOUT_GEN} GEN or less.`;
    } catch {
      errors.payout = "Enter a valid GEN amount (e.g. 10 or 25).";
    }
    return errors;
  };

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    if (!wallet.address) {
      setSubmitError("Connect your wallet first.");
      return;
    }
    const errors = validate();
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setBusy(true);
    try {
      const txHash = await contract.createPolicy(
        metric,
        lat.trim(),
        lon.trim(),
        startDate,
        endDate,
        threshold.trim(),
        condition,
        parseGen(premium),
        parseGen(payout),
      );
      await contract.waitForReceipt(txHash);
      navigate("/policies");
    } catch (err) {
      setSubmitError(describeError(err));
      setBusy(false);
    }
  }

  const recapCity =
    city || (lat && lon ? `${lat.trim()}, ${lon.trim()}` : "");
  const recapTrigger = `${metric} ${condition} ${threshold.trim() || "–"}${units}`;

  return (
    <div className="page container">
      <div className="page-head" data-reveal>
        <span className="kicker">Become the insurer</span>
        <h1>Issue a policy</h1>
        <p className="muted">
          Lock the payout in escrow and set the premium a buyer pays for
          coverage. When the window closes, validators read the Open-Meteo
          archive. Trigger hit, the buyer is paid; missed, the pot returns to
          you. <strong>No claim is ever filed.</strong>
        </p>
      </div>

      {submitError && <div className="error-banner">{submitError}</div>}
      {!wallet.address && (
        <div className="notice">
          Connect your wallet to issue a policy. StudioNet is gasless, so
          issuing only needs the payout amount; it sits in escrow until the
          window settles.
        </div>
      )}

      <div className="side-layout">
      <form className="form panel" onSubmit={onSubmit} noValidate>
        <label>
          What does it cover?
          <div className="side-picker" role="radiogroup" aria-label="Metric">
            <button
              type="button"
              className={`side-option side-opt-rain ${
                metric === "rainfall" ? "selected" : ""
              }`}
              aria-pressed={metric === "rainfall"}
              onClick={() => setMetric("rainfall")}
            >
              <span className="side-sign">
                <DropletIcon size={15} /> Rainfall
              </span>
              <span>sum over the window, in mm</span>
            </button>
            <button
              type="button"
              className={`side-option side-opt-temp ${
                metric === "temperature" ? "selected" : ""
              }`}
              aria-pressed={metric === "temperature"}
              onClick={() => setMetric("temperature")}
            >
              <span className="side-sign">
                <ThermometerIcon size={15} /> Temperature
              </span>
              <span>max daily temperature, in °C</span>
            </button>
          </div>
        </label>

        <label>
          Location (decimal degrees)
          <div className="preset-row">
            {PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                className={`preset-chip ${city === p.label ? "active" : ""}`}
                onClick={() => pickPreset(p.label)}
              >
                {p.label}
              </button>
            ))}
            <button
              type="button"
              className={`preset-chip ${city === "" ? "active" : ""}`}
              onClick={() => setCity("")}
            >
              Custom
            </button>
          </div>
          <div className="coord-row">
            <input
              type="text"
              inputMode="decimal"
              value={lat}
              onChange={(e) => {
                setLat(e.target.value);
                setCity("");
              }}
              placeholder="latitude (e.g. -6.2)"
              aria-label="Latitude"
              aria-invalid={!!fieldErrors.coords || undefined}
            />
            <input
              type="text"
              inputMode="decimal"
              value={lon}
              onChange={(e) => {
                setLon(e.target.value);
                setCity("");
              }}
              placeholder="longitude (e.g. 106.8)"
              aria-label="Longitude"
              aria-invalid={!!fieldErrors.coords || undefined}
            />
          </div>
          {fieldErrors.coords && (
            <span className="field-error">{fieldErrors.coords}</span>
          )}
        </label>

        <div className="form-row-2">
          <label>
            Window start (UTC)
            <input
              type="date"
              value={startDate}
              max={endDate}
              onChange={(e) => setStartDate(e.target.value)}
              aria-invalid={!!fieldErrors.dates || undefined}
            />
          </label>
          <label>
            Window end (UTC)
            <input
              type="date"
              value={endDate}
              min={startDate}
              onChange={(e) => setEndDate(e.target.value)}
              aria-invalid={!!fieldErrors.dates || undefined}
            />
          </label>
        </div>
        {fieldErrors.dates && (
          <span className="field-error">{fieldErrors.dates}</span>
        )}

        <label>
          Trigger condition
          <div className="side-picker" role="radiogroup" aria-label="Condition">
            <button
              type="button"
              className={`side-option side-opt-below ${
                condition === "below" ? "selected" : ""
              }`}
              aria-pressed={condition === "below"}
              onClick={() => setCondition("below")}
            >
              <span className="side-sign">below</span>
              <span>
                {metric === "rainfall"
                  ? "drought: drier than the threshold"
                  : "cold snap: cooler than the threshold"}
              </span>
            </button>
            <button
              type="button"
              className={`side-option side-opt-above ${
                condition === "above" ? "selected" : ""
              }`}
              aria-pressed={condition === "above"}
              onClick={() => setCondition("above")}
            >
              <span className="side-sign">above</span>
              <span>
                {metric === "rainfall"
                  ? "flood: wetter than the threshold"
                  : "heatwave: hotter than the threshold"}
              </span>
            </button>
          </div>
        </label>

        <label>
          Threshold ({units})
          <input
            type="text"
            inputMode="decimal"
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            placeholder={thresholdPlaceholder}
            aria-invalid={!!fieldErrors.threshold || undefined}
          />
          {fieldErrors.threshold && (
            <span className="field-error">{fieldErrors.threshold}</span>
          )}
        </label>

        {humanTrigger && (
          <div className="preview-trigger">
            Pays out when {humanTrigger} over the window.
          </div>
        )}

        <div className="form-row-2">
          <label>
            Premium (GEN, what a buyer pays)
            <input
              type="text"
              inputMode="decimal"
              value={premium}
              onChange={(e) => setPremium(e.target.value)}
              placeholder="e.g. 0.5"
              aria-invalid={!!fieldErrors.premium || undefined}
            />
            {fieldErrors.premium && (
              <span className="field-error">{fieldErrors.premium}</span>
            )}
          </label>
          <label>
            Payout (GEN, locked as escrow)
            <input
              type="text"
              inputMode="decimal"
              value={payout}
              onChange={(e) => setPayout(e.target.value)}
              placeholder={`e.g. 5 (max ${MAX_PAYOUT_GEN})`}
              aria-invalid={!!fieldErrors.payout || undefined}
            />
            {fieldErrors.payout && (
              <span className="field-error">{fieldErrors.payout}</span>
            )}
          </label>
        </div>

        <button
          className="primary"
          type="submit"
          disabled={busy || !wallet.address}
        >
          {busy
            ? "Issuing…"
            : payout.trim()
              ? `Lock ${payout.trim()} GEN as payout`
              : "Lock the payout in escrow"}
        </button>
      </form>

      <aside className="sticky-rail" data-reveal>
        <div className="rail-card">
          <h4 className="rail-title">
            <ShieldIcon size={16} /> Coverage recap
          </h4>
          <div className="rail-row">
            <span className="rk">Trigger</span>
            <span className="rv rv-sky">{recapTrigger}</span>
          </div>
          <div className="rail-row">
            <span className="rk">Location</span>
            <span className="rv">{recapCity || "–"}</span>
          </div>
          <div className="rail-row">
            <span className="rk">Window</span>
            <span className="rv">
              {startDate} to {endDate}
            </span>
          </div>
          <div className="rail-row">
            <span className="rk">Premium</span>
            <span className="rv">{premium.trim() || "–"} GEN</span>
          </div>
          <div className="rail-row">
            <span className="rk">Escrow</span>
            <span className="rv rv-sun">{payout.trim() || "–"} GEN</span>
          </div>
          <p className="rail-note">
            You send the payout now. It sits in escrow until the window
            settles, and buying closes the moment the window ends.
          </p>
        </div>

        <div className="rail-card">
          <h4 className="rail-title">
            <BoltIcon size={16} /> How it settles
          </h4>
          <ul>
            <li>Window closes, then anyone can trigger settlement.</li>
            <li>
              Validators fetch the Open-Meteo archive and must agree
              byte-for-byte.
            </li>
            <li>Trigger hit, buyer paid. Missed, pot back to you.</li>
          </ul>
        </div>
      </aside>
      </div>
    </div>
  );
}
