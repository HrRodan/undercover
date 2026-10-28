import type { ClaimStatus, ClaimStep } from "../types";

export interface AgentStepsProps {
  steps: ClaimStep[];
  status: ClaimStatus;
}

export function AgentSteps({ steps, status }: Readonly<AgentStepsProps>) {
  return (
    <div className="section-block" aria-label="Agent Activity">
      <div className="panel-header">
        <h3 className="section-title">Agent Step-by-Step Activity</h3>
        {status === "in_progress" ? (
          <span className="status-badge badge-cyan">Working live</span>
        ) : null}
      </div>

      {steps.length === 0 ? (
        <p className="accent-callout">
          No agent steps recorded yet. Run the UnderCover Agent to evaluate this
          claim.
        </p>
      ) : (
        <ol className="step-list">
          {steps.map((step) => (
            <li key={step.step_number} className="step-item">
              <span className="step-index">
                {String(step.step_number).padStart(2, "0")}
              </span>
              <span>{step.message}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
