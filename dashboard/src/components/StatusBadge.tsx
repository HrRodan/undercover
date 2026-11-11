import { formatClaimType } from "../api";
import type {
  ClaimDecision,
  ClaimStatus,
  PaymentStatus,
  TodoStatus,
} from "../types";

export type BadgeVariant = "emerald" | "amber" | "cyan" | "indigo" | "rose";

const STATUS_CONFIG: Record<
  ClaimStatus,
  { label: string; variant: BadgeVariant }
> = {
  waiting: { label: "Waiting", variant: "indigo" },
  in_progress: { label: "In progress", variant: "cyan" },
  waiting_for_sign_off: {
    label: "Waiting for sign-off",
    variant: "amber",
  },
  decided: { label: "Decided", variant: "emerald" },
  left_for_handler: {
    label: "Left for handler",
    variant: "rose",
  },
};

const TODO_CONFIG: Record<
  TodoStatus,
  { label: string; variant: BadgeVariant }
> = {
  to_do: { label: "To do", variant: "indigo" },
  in_progress: { label: "In progress", variant: "cyan" },
  done: { label: "Done", variant: "emerald" },
  left_for_handler: { label: "Left for handler", variant: "rose" },
};

const DECISION_CONFIG: Record<
  ClaimDecision,
  { label: string; variant: BadgeVariant }
> = {
  approve: { label: "Approved", variant: "emerald" },
  decline: { label: "Declined", variant: "rose" },
  refer: { label: "Referred", variant: "cyan" },
};

const PAYMENT_CONFIG: Record<
  PaymentStatus,
  { label: string; variant: BadgeVariant }
> = {
  unpaid: { label: "Unpaid", variant: "indigo" },
  pending_sign_off: {
    label: "Pending sign-off",
    variant: "amber",
  },
  paid: { label: "Paid", variant: "emerald" },
};

const CLAIM_TYPE_VARIANTS: Record<string, BadgeVariant> = {
  emergency_medical: "rose",
  trip_cancellation: "amber",
  trip_delay: "cyan",
  baggage_delay: "cyan",
  baggage: "indigo",
  passport: "emerald",
};

const CATEGORY_VARIANTS: Record<string, BadgeVariant> = {
  medical: "rose",
  accommodation: "indigo",
  meals: "cyan",
  transport: "cyan",
  electronics: "amber",
  carrier_report: "cyan",
  invoice: "amber",
  receipt: "emerald",
  police_report: "rose",
};

export function SemanticBadge({
  label,
  variant,
}: Readonly<{ label: string; variant: BadgeVariant }>) {
  return (
    <span className={`status-badge badge-${variant}`}>
      <span className="badge-dot" aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

export function ClaimStatusBadge({
  status,
}: Readonly<{ status: ClaimStatus }>) {
  const config = STATUS_CONFIG[status];
  return <SemanticBadge label={config.label} variant={config.variant} />;
}

export function TodoStatusBadge({ status }: Readonly<{ status: TodoStatus }>) {
  const config = TODO_CONFIG[status];
  return <SemanticBadge label={config.label} variant={config.variant} />;
}

export function DecisionBadge({
  decision,
}: Readonly<{ decision: ClaimDecision | null }>) {
  if (!decision) {
    return <SemanticBadge label="Pending" variant="indigo" />;
  }
  const config = DECISION_CONFIG[decision];
  return <SemanticBadge label={config.label} variant={config.variant} />;
}

export function PaymentStatusBadge({
  paymentStatus,
}: Readonly<{ paymentStatus: PaymentStatus }>) {
  const config = PAYMENT_CONFIG[paymentStatus];
  return <SemanticBadge label={config.label} variant={config.variant} />;
}

export function ClaimTypeBadge({ claimType }: Readonly<{ claimType: string }>) {
  const variant = CLAIM_TYPE_VARIANTS[claimType] ?? "indigo";
  return <SemanticBadge label={formatClaimType(claimType)} variant={variant} />;
}

export function CategoryBadge({ category }: Readonly<{ category: string }>) {
  const variant = CATEGORY_VARIANTS[category] ?? "indigo";
  return <SemanticBadge label={category} variant={variant} />;
}

export function SectionReadBadge({ section }: Readonly<{ section: string }>) {
  const variant: BadgeVariant = section.startsWith("Claims Manual")
    ? "cyan"
    : "indigo";
  return <SemanticBadge label={section} variant={variant} />;
}
