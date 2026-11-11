import { useState } from "react";
import { formatUsd } from "../api";
import type { ClaimStatus, ClaimSummary, TodoItem } from "../types";
import {
  type BadgeVariant,
  ClaimStatusBadge,
  ClaimTypeBadge,
  DecisionBadge,
} from "./StatusBadge";
import { TodoListPanel } from "./TodoListPanel";

type FilterValue = "all" | ClaimStatus;

const STATUS_METRICS: {
  status: ClaimStatus;
  label: string;
  variant: BadgeVariant;
}[] = [
  { status: "waiting", label: "Waiting", variant: "indigo" },
  { status: "in_progress", label: "In progress", variant: "cyan" },
  {
    status: "waiting_for_sign_off",
    label: "Waiting for sign-off",
    variant: "amber",
  },
  { status: "decided", label: "Decided", variant: "emerald" },
  { status: "left_for_handler", label: "Left for handler", variant: "rose" },
];

const FILTER_OPTIONS: {
  value: FilterValue;
  label: string;
  variant: BadgeVariant;
}[] = [
  { value: "all", label: "All", variant: "indigo" },
  ...STATUS_METRICS.map((item) => ({
    value: item.status,
    label: item.label,
    variant: item.variant,
  })),
];

export interface ClaimsQueueProps {
  claims: ClaimSummary[];
  todos: TodoItem[];
  runSummary: string;
  selectedClaimId: string | null;
  isRunningQueue: boolean;
  onSelectClaim: (claimId: string) => void;
  onRunAllWaiting: (cap: number) => void;
  onResetQueue: () => void;
}

export function ClaimsQueue({
  claims,
  todos,
  runSummary,
  selectedClaimId,
  isRunningQueue,
  onSelectClaim,
  onRunAllWaiting,
  onResetQueue,
}: Readonly<ClaimsQueueProps>) {
  const [filter, setFilter] = useState<FilterValue>("all");
  const [cap, setCap] = useState<number>(25);

  const filteredClaims =
    filter === "all" ? claims : claims.filter((c) => c.status === filter);

  const waitingCount = claims.filter((c) => c.status === "waiting").length;

  return (
    <section className="panel" aria-label="Claims Queue">
      <div className="panel-header">
        <div>
          <h2>Claims Queue</h2>
          <p className="brand-subtitle">
            {String(claims.length)} total claims in queue
          </p>
        </div>
        <div className="topbar-controls">
          <label htmlFor="run-cap-select" className="brand-subtitle">
            Cap:
          </label>
          <select
            id="run-cap-select"
            className="handler-select"
            aria-label="Run cap"
            value={String(cap)}
            disabled={isRunningQueue}
            onChange={(e) => {
              setCap(Number(e.target.value));
            }}
          >
            <option value="5">5 claims</option>
            <option value="10">10 claims</option>
            <option value="25">All waiting (25)</option>
          </select>
          <button
            type="button"
            className="btn-secondary"
            disabled={isRunningQueue}
            onClick={onResetQueue}
          >
            Reset Queue
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={isRunningQueue || waitingCount === 0}
            onClick={() => {
              onRunAllWaiting(cap);
            }}
          >
            {isRunningQueue
              ? "Running Queue..."
              : `Run All Waiting (${String(waitingCount)})`}
          </button>
        </div>
      </div>

      <div className="metrics-row">
        {STATUS_METRICS.map((item) => {
          const count = claims.filter((c) => c.status === item.status).length;
          return (
            <div
              key={item.status}
              className={`metric-card metric-${item.variant}`}
            >
              <div className="metric-label">
                <span className="badge-dot" aria-hidden="true" />
                <span>{item.label}</span>
              </div>
              <div className="metric-value">{String(count)}</div>
            </div>
          );
        })}
      </div>

      <TodoListPanel todos={todos} summary={runSummary} />

      <div className="filter-tabs" role="group" aria-label="Filter queue">
        {FILTER_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            className={`filter-pill pill-${option.variant} ${filter === option.value ? "active" : ""}`}
            aria-pressed={filter === option.value}
            onClick={() => {
              setFilter(option.value);
            }}
          >
            {option.value !== "all" ? (
              <span className="badge-dot" aria-hidden="true" />
            ) : null}
            <span>{option.label}</span>
          </button>
        ))}
      </div>

      <div className="table-scroll">
        <table className="data-table queue-table">
          <thead>
            <tr>
              <th scope="col">Claim</th>
              <th scope="col">Policy</th>
              <th scope="col">Type</th>
              <th scope="col">Status</th>
              <th scope="col">Decision</th>
              <th scope="col" className="amount-cell">
                Claimed
              </th>
              <th scope="col" className="amount-cell">
                Payout
              </th>
            </tr>
          </thead>
          <tbody>
            {filteredClaims.map((claim) => {
              const isSelected = claim.claim_id === selectedClaimId;
              return (
                <tr
                  key={claim.claim_id}
                  className={`queue-row ${isSelected ? "selected" : ""}`}
                >
                  <td data-label="Claim">
                    <button
                      type="button"
                      className="claim-select-btn"
                      onClick={() => {
                        onSelectClaim(claim.claim_id);
                      }}
                    >
                      {claim.claim_id}
                    </button>
                  </td>
                  <td data-label="Policy" className="mono-num">
                    {claim.policy_id}
                  </td>
                  <td data-label="Type">
                    <ClaimTypeBadge claimType={claim.claim_type} />
                  </td>
                  <td data-label="Status">
                    <ClaimStatusBadge status={claim.status} />
                  </td>
                  <td data-label="Decision">
                    <DecisionBadge decision={claim.decision} />
                  </td>
                  <td data-label="Claimed" className="amount-cell">
                    {formatUsd(claim.amount_claimed)}
                  </td>
                  <td data-label="Payout" className="amount-cell">
                    {claim.payout !== null ? formatUsd(claim.payout) : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
