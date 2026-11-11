import type {
  ClaimsManualResponse,
  InstructionsResponse,
  PolicyWordingResponse,
} from "../types";
import { SemanticBadge } from "./StatusBadge";

export interface InstructionsViewProps {
  instructions: InstructionsResponse;
  policyWording: PolicyWordingResponse | null;
  claimsManual: ClaimsManualResponse | null;
}

export function InstructionsView({
  instructions,
  policyWording,
  claimsManual,
}: Readonly<InstructionsViewProps>) {
  return (
    <div className="workspace">
      <div className="detail-stack">
        <section className="panel" aria-label="Agent Instructions">
          <div className="panel-header">
            <div>
              <h2>Agent Instructions</h2>
              <p className="brand-subtitle">
                Instructions for running the queue and for working a claim (Read
                only)
              </p>
            </div>
            <SemanticBadge label="Read only" variant="indigo" />
          </div>

          {instructions.queue_instructions ? (
            <div className="detail-stack">
              <div>
                <h3 className="section-title">
                  Queue Agent Instructions (Medium Reasoning)
                </h3>
                <pre className="code-well">
                  {instructions.queue_instructions}
                </pre>
              </div>
              <div>
                <h3 className="section-title">
                  Claim Subagent Instructions (Low Reasoning)
                </h3>
                <pre className="code-well">
                  {instructions.claim_instructions}
                </pre>
              </div>
            </div>
          ) : (
            <pre className="code-well">{instructions.instructions}</pre>
          )}
        </section>
      </div>

      <div className="detail-stack">
        <section className="panel" aria-label="Policy Wording">
          <div className="panel-header">
            <div>
              <h2>Policy Wording Reference</h2>
              <p className="brand-subtitle">
                Version {policyWording?.version ?? "2026.1"} — Contractual rules
              </p>
            </div>
            <SemanticBadge label="Active" variant="emerald" />
          </div>
          <pre className="code-well">{policyWording?.content ?? ""}</pre>
        </section>

        {claimsManual ? (
          <section className="panel" aria-label="Claims Manual">
            <div className="panel-header">
              <div>
                <h2>Claims Handling Manual</h2>
                <p className="brand-subtitle">
                  Version {claimsManual.version} — Internal handler guidelines
                </p>
              </div>
              <SemanticBadge label="Active" variant="cyan" />
            </div>
            <pre className="code-well">{claimsManual.content}</pre>
          </section>
        ) : null}
      </div>
    </div>
  );
}
