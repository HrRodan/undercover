import type { PolicyWordingResponse } from "../types";

export interface InstructionsViewProps {
  instructions: string;
  policyWording: PolicyWordingResponse | null;
}

export function InstructionsView({
  instructions,
  policyWording,
}: Readonly<InstructionsViewProps>) {
  return (
    <div className="workspace">
      <section className="panel" aria-label="Agent Instructions">
        <div className="panel-header">
          <div>
            <h2>Agent Instructions</h2>
            <p className="brand-subtitle">
              System prompt used by the UnderCover Agent (Read only)
            </p>
          </div>
          <span className="status-badge badge-indigo">Read only</span>
        </div>
        <pre className="code-well">{instructions}</pre>
      </section>

      <section className="panel" aria-label="Policy Wording">
        <div className="panel-header">
          <div>
            <h2>Policy Wording Reference</h2>
            <p className="brand-subtitle">
              Version {policyWording?.version ?? "2026.1"} — Contractual rules
            </p>
          </div>
          <span className="status-badge badge-emerald">Active</span>
        </div>
        <pre className="code-well">{policyWording?.content ?? ""}</pre>
      </section>
    </div>
  );
}
