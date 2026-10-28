import type { ClaimDecision, ClaimStatus, PaymentStatus } from "../types";

const STATUS_LABELS: Record<ClaimStatus, { label: string; className: string }> =
  {
    waiting: { label: "Waiting", className: "badge-indigo" },
    in_progress: { label: "In progress", className: "badge-cyan" },
    waiting_for_sign_off: {
      label: "Waiting for sign-off",
      className: "badge-amber",
    },
    decided: { label: "Decided", className: "badge-emerald" },
  };

const DECISION_LABELS: Record<
  ClaimDecision,
  { label: string; className: string }
> = {
  approve: { label: "Approved", className: "badge-emerald" },
  decline: { label: "Declined", className: "badge-rose" },
  refer: { label: "Referred", className: "badge-cyan" },
};

const PAYMENT_LABELS: Record<
  PaymentStatus,
  { label: string; className: string }
> = {
  unpaid: { label: "Unpaid", className: "badge-indigo" },
  pending_sign_off: {
    label: "Pending sign-off",
    className: "badge-amber",
  },
  paid: { label: "Paid", className: "badge-emerald" },
};

export function ClaimStatusBadge({
  status,
}: Readonly<{ status: ClaimStatus }>) {
  const config = STATUS_LABELS[status];
  return (
    <span className={`status-badge ${config.className}`}>{config.label}</span>
  );
}

export function DecisionBadge({
  decision,
}: Readonly<{ decision: ClaimDecision | null }>) {
  if (!decision) {
    return <span className="status-badge badge-indigo">Pending</span>;
  }
  const config = DECISION_LABELS[decision];
  return (
    <span className={`status-badge ${config.className}`}>{config.label}</span>
  );
}

export function PaymentStatusBadge({
  paymentStatus,
}: Readonly<{ paymentStatus: PaymentStatus }>) {
  const config = PAYMENT_LABELS[paymentStatus];
  return (
    <span className={`status-badge ${config.className}`}>{config.label}</span>
  );
}
