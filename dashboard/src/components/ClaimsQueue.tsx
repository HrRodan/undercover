import { useState } from "react";
import { formatClaimType, formatUsd } from "../api";
import type { ClaimStatus, ClaimSummary } from "../types";
import { ClaimStatusBadge, DecisionBadge } from "./StatusBadge";

type FilterValue = "all" | ClaimStatus;

const FILTER_OPTIONS: { value: FilterValue; label: string }[] = [
  { value: "all", label: "All" },
  { value: "waiting", label: "Waiting" },
  { value: "in_progress", label: "In progress" },
  { value: "waiting_for_sign_off", label: "Waiting for sign-off" },
  { value: "decided", label: "Decided" },
];

export interface ClaimsQueueProps {
  claims: ClaimSummary[];
  selectedClaimId: string | null;
  onSelectClaim: (claimId: string) => void;
}

export function ClaimsQueue({
  claims,
  selectedClaimId,
  onSelectClaim,
}: Readonly<ClaimsQueueProps>) {
  const [filter, setFilter] = useState<FilterValue>("all");

  const filteredClaims =
    filter === "all" ? claims : claims.filter((c) => c.status === filter);

  const waitingCount = claims.filter((c) => c.status === "waiting").length;
  const inProgressCount = claims.filter(
    (c) => c.status === "in_progress",
  ).length;
  const signOffCount = claims.filter(
    (c) => c.status === "waiting_for_sign_off",
  ).length;
  const decidedCount = claims.filter((c) => c.status === "decided").length;

  return (
    <section className="panel" aria-label="Claims Queue">
      <div className="panel-header">
        <div>
          <h2>Claims Queue</h2>
          <p className="brand-subtitle">
            {String(claims.length)} total claims in queue
          </p>
        </div>
      </div>

      <div className="metrics-row">
        <div className="metric-card">
          <div className="metric-label">Waiting</div>
          <div className="metric-value">{String(waitingCount)}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">In progress</div>
          <div className="metric-value">{String(inProgressCount)}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Waiting for sign-off</div>
          <div className="metric-value">{String(signOffCount)}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Decided</div>
          <div className="metric-value">{String(decidedCount)}</div>
        </div>
      </div>

      <div className="filter-tabs" role="group" aria-label="Filter queue">
        {FILTER_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            className={`filter-pill ${filter === option.value ? "active" : ""}`}
            aria-pressed={filter === option.value}
            onClick={() => {
              setFilter(option.value);
            }}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="table-scroll">
        <table className="data-table">
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
                  <td>
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
                  <td className="mono-num">{claim.policy_id}</td>
                  <td>{formatClaimType(claim.claim_type)}</td>
                  <td>
                    <ClaimStatusBadge status={claim.status} />
                  </td>
                  <td>
                    <DecisionBadge decision={claim.decision} />
                  </td>
                  <td className="amount-cell">
                    {formatUsd(claim.amount_claimed)}
                  </td>
                  <td className="amount-cell">
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
