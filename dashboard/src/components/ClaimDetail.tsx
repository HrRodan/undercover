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
  CategoryBadge,
  ClaimStatusBadge,
  DecisionBadge,
  PaymentStatusBadge,
  SectionReadBadge,
  SemanticBadge,
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

      {claim.reason ? <p className="decision-reason">{claim.reason}</p> : null}

      {claim.status === "waiting_for_sign_off" ? (
        <div className="sign-off-banner">
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

function SectionsReadSection({
  sectionsRead,
}: Readonly<{ sectionsRead: string[] }>) {
  return (
    <div className="section-block" aria-label="Sections Read">
      <h3 className="section-title">
        Policy Wording &amp; Manual Sections Read
      </h3>
      {sectionsRead.length === 0 ? (
        <p className="accent-callout compact-text">
          No wording or manual sections read on this claim yet.
        </p>
      ) : (
        <div className="badge-cluster">
          {sectionsRead.map((sec) => (
            <SectionReadBadge key={sec} section={sec} />
          ))}
        </div>
      )}
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
          <div className="panel-header compact-header">
            <h3 className="section-title compact-text">
              Policy &amp; Plan Coverage
            </h3>
            <SemanticBadge label={policy.status} variant="emerald" />
          </div>
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
            <ul className="history-list">
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
            <p className="history-empty">No prior claims on file.</p>
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

        <SectionsReadSection sectionsRead={claim.sections_read ?? []} />

        <AgentSteps steps={claim.steps} status={claim.status} />

        <div className="section-block">
          <h3 className="section-title">Customer Story</h3>
          <p className="compact-text">{claim.story}</p>
        </div>

        <div className="section-block">
          <h3 className="section-title">
            Claimed Items (Total:{" "}
            <span className="mono-num">{formatUsd(claim.amount_claimed)}</span>)
          </h3>
          <div className="table-scroll">
            <table className="data-table items-table">
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
                    <td data-label="Description">{item.description}</td>
                    <td data-label="Category">
                      <CategoryBadge category={item.category} />
                    </td>
                    <td data-label="Amount" className="amount-cell">
                      {formatUsd(item.amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="section-block">
          <h3 className="section-title">Supporting Documents</h3>
          <div className="detail-stack">
            {claim.documents.map((doc) => (
              <div key={doc.name}>
                <div className="doc-header">
                  <strong>{doc.name}</strong>
                  <CategoryBadge category={doc.type} />
                </div>
                <pre className="code-well doc-pre">{doc.content}</pre>
              </div>
            ))}
          </div>
        </div>

        <PolicyAndCustomerSection policy={policy} customer={customer} />
      </div>
    </section>
  );
}
