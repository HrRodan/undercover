import { useState } from "react";
import { formatClaimType, formatUsd } from "../api";
import type {
  ClaimDetail as ClaimDetailModel,
  CustomerDetail,
  HandlerDetail,
  PolicyDetail,
} from "../types";
import { AgentSteps } from "./AgentSteps";
import {
  ClaimStatusBadge,
  DecisionBadge,
  PaymentStatusBadge,
} from "./StatusBadge";

export interface ClaimDetailProps {
  claim: ClaimDetailModel | null;
  policy: PolicyDetail | null;
  customer: CustomerDetail | null;
  handlers: HandlerDetail[];
  isRunning: boolean;
  onRunAgent: (claimId: string) => void;
  onSignOff: (claimId: string, handlerId: string) => void;
}

function DecisionSection({
  claim,
  handlers,
  onSignOff,
}: Readonly<{
  claim: ClaimDetailModel;
  handlers: HandlerDetail[];
  onSignOff: (claimId: string, handlerId: string) => void;
}>) {
  const defaultHandler = handlers[0]?.handler_id ?? "HND-01";
  const [selectedHandler, setSelectedHandler] =
    useState<string>(defaultHandler);

  return (
    <div className="section-block" aria-label="Agent Decision">
      <h3 className="section-title">Agent Decision &amp; Payout</h3>
      <div className="meta-grid">
        <div className="meta-item">
          <span className="meta-label">Decision</span>
          <div className="meta-value">
            <DecisionBadge decision={claim.decision} />
          </div>
        </div>
        <div className="meta-item">
          <span className="meta-label">Approved Payout</span>
          <span className="meta-value mono-num">
            {claim.payout !== null ? formatUsd(claim.payout) : "—"}
          </span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Payment Status</span>
          <div className="meta-value">
            <PaymentStatusBadge paymentStatus={claim.payment_status} />
          </div>
        </div>
        <div className="meta-item">
          <span className="meta-label">Amount Paid</span>
          <span className="meta-value mono-num">
            {formatUsd(claim.amount_paid)}
          </span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Policy Section</span>
          <span className="meta-value">{claim.policy_section ?? "—"}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Signed Off By</span>
          <span className="meta-value mono-num">
            {claim.signed_off_by ?? "—"}
          </span>
        </div>
      </div>

      {claim.reason ? (
        <p style={{ marginTop: "12px", marginBottom: 0 }}>{claim.reason}</p>
      ) : null}

      {claim.status === "waiting_for_sign_off" ? (
        <div className="sign-off-banner" style={{ marginTop: "14px" }}>
          <div>
            <strong>Handler sign-off required:</strong> Payout of{" "}
            <span className="mono-num">{formatUsd(claim.payout ?? 0)}</span>{" "}
            exceeds the $1,000.00 automatic payment limit and is blocked until a
            handler signs off.
          </div>
          <div className="sign-off-controls">
            <label htmlFor="handler-select">Handler:</label>
            <select
              id="handler-select"
              className="handler-select"
              value={selectedHandler}
              onChange={(e) => {
                setSelectedHandler(e.target.value);
              }}
            >
              {handlers.map((h) => (
                <option key={h.handler_id} value={h.handler_id}>
                  {h.name} ({h.handler_id})
                </option>
              ))}
            </select>
            <button
              type="button"
              className="btn-amber"
              onClick={() => {
                onSignOff(claim.claim_id, selectedHandler);
              }}
            >
              Sign Off &amp; Release Payment
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function PolicyAndCustomerSection({
  policy,
  customer,
}: Readonly<{
  policy: PolicyDetail | null;
  customer: CustomerDetail | null;
}>) {
  return (
    <div className="meta-grid">
      {policy ? (
        <div className="section-block">
          <h3 className="section-title">Policy &amp; Plan Coverage</h3>
          <div className="meta-grid">
            <div className="meta-item">
              <span className="meta-label">Policy ID</span>
              <span className="meta-value mono-num">{policy.policy_id}</span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Plan</span>
              <span className="meta-value">{policy.plan_details.name}</span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Trip Destination</span>
              <span className="meta-value">{policy.trip.destination}</span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Covered Trip Dates</span>
              <span className="meta-value mono-num">
                {policy.trip.departs_on} to {policy.trip.returns_on}
              </span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Deductible</span>
              <span className="meta-value mono-num">
                {formatUsd(policy.plan_details.deductible)}
              </span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Per-Item Limit</span>
              <span className="meta-value mono-num">
                {formatUsd(policy.plan_details.per_item_limit)}
              </span>
            </div>
          </div>
        </div>
      ) : null}

      {customer ? (
        <div className="section-block">
          <h3 className="section-title">Customer &amp; Claim History</h3>
          <div className="meta-grid">
            <div className="meta-item">
              <span className="meta-label">Customer</span>
              <span className="meta-value">
                {customer.name} ({customer.customer_id})
              </span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Prior Claims</span>
              <span className="meta-value mono-num">
                {String(customer.previous_claims.length)}
              </span>
            </div>
          </div>
          {customer.previous_claims.length > 0 ? (
            <ul style={{ margin: "10px 0 0 0", paddingLeft: "18px" }}>
              {customer.previous_claims.map((prev) => (
                <li key={prev.claim_id}>
                  <span className="mono-num">{prev.claim_id}</span> (
                  {prev.filed_on}): {prev.summary} —{" "}
                  <span className="mono-num">
                    {formatUsd(prev.amount_paid)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p style={{ margin: "10px 0 0 0" }}>No prior claims on file.</p>
          )}
        </div>
      ) : null}
    </div>
  );
}

export function ClaimDetail({
  claim,
  policy,
  customer,
  handlers,
  isRunning,
  onRunAgent,
  onSignOff,
}: Readonly<ClaimDetailProps>) {
  if (!claim) {
    return (
      <section className="panel" aria-label="Claim Detail">
        <p className="accent-callout">
          Select a claim from the queue to inspect its full record.
        </p>
      </section>
    );
  }

  const isBusy = isRunning || claim.status === "in_progress";
  const hasRunBefore =
    claim.decision !== null ||
    claim.status === "decided" ||
    claim.status === "waiting_for_sign_off";
  let runButtonLabel = "Run Agent";
  if (isBusy) {
    runButtonLabel = "Running Agent...";
  } else if (hasRunBefore) {
    runButtonLabel = "Rerun Agent";
  }

  return (
    <section className="panel" aria-label="Claim Detail">
      <div className="panel-header">
        <div>
          <h2>
            <span className="mono-num">{claim.claim_id}</span> — {claim.summary}
          </h2>
          <p className="brand-subtitle">
            {formatClaimType(claim.claim_type)} in {claim.incident_location} on{" "}
            <span className="mono-num">{claim.incident_date}</span>
          </p>
        </div>
        <div className="topbar-controls">
          <ClaimStatusBadge status={claim.status} />
          <button
            type="button"
            className="btn-primary"
            disabled={isBusy}
            onClick={() => {
              onRunAgent(claim.claim_id);
            }}
          >
            {runButtonLabel}
          </button>
        </div>
      </div>

      <div className="detail-stack">
        <DecisionSection
          claim={claim}
          handlers={handlers}
          onSignOff={onSignOff}
        />

        <AgentSteps steps={claim.steps} status={claim.status} />

        <div className="section-block">
          <h3 className="section-title">Customer Story</h3>
          <p style={{ margin: 0 }}>{claim.story}</p>
        </div>

        <div className="section-block">
          <h3 className="section-title">
            Claimed Items (Total:{" "}
            <span className="mono-num">{formatUsd(claim.amount_claimed)}</span>)
          </h3>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Description</th>
                <th scope="col">Category</th>
                <th scope="col" className="amount-cell">
                  Amount
                </th>
              </tr>
            </thead>
            <tbody>
              {claim.items.map((item) => (
                <tr key={item.description}>
                  <td>{item.description}</td>
                  <td>{item.category}</td>
                  <td className="amount-cell">{formatUsd(item.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="section-block">
          <h3 className="section-title">Supporting Documents</h3>
          <div className="detail-stack">
            {claim.documents.map((doc) => (
              <div key={doc.name}>
                <strong>{doc.name}</strong>{" "}
                <span className="brand-subtitle">({doc.type})</span>
                <pre className="code-well" style={{ marginTop: "6px" }}>
                  {doc.content}
                </pre>
              </div>
            ))}
          </div>
        </div>

        <PolicyAndCustomerSection policy={policy} customer={customer} />
      </div>
    </section>
  );
}
