import type { TodoItem } from "../types";
import { TodoStatusBadge } from "./StatusBadge";

export interface TodoListPanelProps {
  todos: TodoItem[];
  summary: string;
}

export function TodoListPanel({
  todos,
  summary,
}: Readonly<TodoListPanelProps>) {
  return (
    <div className="section-block todo-panel" aria-label="Agent To-Do List">
      <div className="panel-header compact-header">
        <h3 className="section-title compact-text">Agent To-Do List</h3>
        <span className="brand-subtitle">
          {String(todos.filter((t) => t.status === "done").length)} of{" "}
          {String(todos.length)} completed
        </span>
      </div>

      {todos.length === 0 ? (
        <p className="accent-callout compact-text">
          No active run to-do list yet. Start a queue run to watch the agent
          plan and tick off claims.
        </p>
      ) : (
        <ol className="step-list">
          {todos.map((item) => (
            <li
              key={`${item.claim_id}-${item.description}`}
              className="step-item todo-item"
            >
              <div>
                <span className="mono-num todo-claim-id">{item.claim_id}</span>{" "}
                <span>— {item.description}</span>
                {item.result_summary ? (
                  <div className="brand-subtitle todo-result">
                    {item.result_summary}
                  </div>
                ) : null}
              </div>
              <TodoStatusBadge status={item.status} />
            </li>
          ))}
        </ol>
      )}

      {summary ? (
        <div className="handover-box">
          <span className="meta-label">Handover Summary</span>
          <pre className="code-well handover-pre">{summary}</pre>
        </div>
      ) : null}
    </div>
  );
}
