import type { PolicyStatus } from "../lib/types";
import { DropletIcon, ThermometerIcon } from "./icons";

const STATUS_LABEL: Record<PolicyStatus, string> = {
  OPEN: "Awaiting buyer",
  ACTIVE: "Coverage live",
  PAID: "Trigger hit · paid",
  EXPIRED: "Trigger missed",
  CANCELLED: "Cancelled",
  REFUNDED: "Unwound",
};

export function StatusBadge({ status }: { status: PolicyStatus }) {
  return (
    <span className={`status-chip st-${status.toLowerCase()}`}>
      {STATUS_LABEL[status]}
    </span>
  );
}

export function MetricBadge({ metric }: { metric: "rainfall" | "temperature" }) {
  return (
    <span className={`metric-chip ${metric}`}>
      {metric === "rainfall" ? (
        <DropletIcon size={12} />
      ) : (
        <ThermometerIcon size={12} />
      )}
      {metric === "rainfall" ? "rainfall" : "temperature"}
    </span>
  );
}
