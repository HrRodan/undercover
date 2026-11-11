import { useCallback, useEffect, useState } from "react";
import {
  fetchClaimDetail,
  fetchClaims,
  fetchClaimsManual,
  fetchCustomerDetail,
  fetchHandlers,
  fetchInstructions,
  fetchPolicyDetail,
  fetchPolicyWording,
  fetchQueueRun,
  resetAllClaims,
  signOffClaim,
  triggerClaimAgent,
  triggerQueueRun,
} from "./api";
import { ClaimDetail } from "./components/ClaimDetail";
import { ClaimsQueue } from "./components/ClaimsQueue";
import { InstructionsView } from "./components/InstructionsView";
import type {
  ClaimDetail as ClaimDetailModel,
  ClaimsManualResponse,
  ClaimSummary,
  CustomerDetail,
  HandlerDetail,
  InstructionsResponse,
  PolicyDetail,
  PolicyWordingResponse,
  TodoItem,
} from "./types";

type ActiveTab = "workspace" | "instructions";

function Topbar({
  activeTab,
  theme,
  onSelectTab,
  onToggleTheme,
}: Readonly<{
  activeTab: ActiveTab;
  theme: "light" | "dark";
  onSelectTab: (tab: ActiveTab) => void;
  onToggleTheme: () => void;
}>) {
  return (
    <header className="topbar">
      <div className="brand-group">
        <h1 className="brand-title">UnderCover</h1>
        <span className="brand-subtitle">Travel Insurance Claims Platform</span>
      </div>

      <div className="topbar-controls">
        <nav className="nav-tabs" aria-label="Main navigation">
          <button
            type="button"
            className={`nav-tab ${activeTab === "workspace" ? "active" : ""}`}
            onClick={() => {
              onSelectTab("workspace");
            }}
          >
            Claims Workspace
          </button>
          <button
            type="button"
            className={`nav-tab ${activeTab === "instructions" ? "active" : ""}`}
            onClick={() => {
              onSelectTab("instructions");
            }}
          >
            Agent Instructions
          </button>
        </nav>

        <button type="button" className="btn-secondary" onClick={onToggleTheme}>
          {theme === "light" ? "Dark mode" : "Light mode"}
        </button>
      </div>
    </header>
  );
}

function isWorkspaceBusy(
  isRunning: boolean,
  isRunningQueue: boolean,
  claimDetail: ClaimDetailModel | null,
  claims: ClaimSummary[],
): boolean {
  return (
    isRunning ||
    isRunningQueue ||
    claimDetail?.status === "in_progress" ||
    claims.some((c) => c.status === "in_progress")
  );
}

export function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("workspace");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [claims, setClaims] = useState<ClaimSummary[]>([]);
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [runSummary, setRunSummary] = useState("");
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);
  const [claimDetail, setClaimDetail] = useState<ClaimDetailModel | null>(null);
  const [policyDetail, setPolicyDetail] = useState<PolicyDetail | null>(null);
  const [customer, setCustomer] = useState<CustomerDetail | null>(null);
  const [handlers, setHandlers] = useState<HandlerDetail[]>([]);
  const [instructions, setInstructions] = useState<InstructionsResponse>({
    instructions: "",
  });
  const [wording, setWording] = useState<PolicyWordingResponse | null>(null);
  const [manual, setManual] = useState<ClaimsManualResponse | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isRunningQueue, setIsRunningQueue] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadSelectedClaimBundle = useCallback(async (claimId: string) => {
    try {
      const detail = await fetchClaimDetail(claimId);
      setClaimDetail(detail);
      const [policy, cust] = await Promise.all([
        fetchPolicyDetail(detail.policy_id),
        fetchCustomerDetail(detail.customer_id),
      ]);
      setPolicyDetail(policy);
      setCustomer(cust);
    } catch {
      setErrorMessage(`Unable to load claim ${claimId}`);
    }
  }, []);

  const refreshQueueRun = useCallback(() => {
    void fetchQueueRun()
      .then((qState) => {
        setTodos(qState.todos);
        setRunSummary(qState.summary);
      })
      .catch(() => null);
  }, []);

  useEffect(() => {
    void Promise.all([
      fetchClaims(),
      fetchHandlers(),
      fetchInstructions(),
      fetchPolicyWording(),
    ])
      .then(
        async ([claimsData, handlersData, instructionsData, wordingDoc]) => {
          setClaims(claimsData);
          setHandlers(handlersData);
          setInstructions(instructionsData);
          setWording(wordingDoc);
          void fetchClaimsManual()
            .then(setManual)
            .catch(() => null);
          refreshQueueRun();
          if (claimsData.length > 0) {
            setSelectedClaimId(claimsData[0].claim_id);
            await loadSelectedClaimBundle(claimsData[0].claim_id);
          }
        },
      )
      .catch(() => {
        setErrorMessage("Backend unavailable");
      });
  }, [loadSelectedClaimBundle, refreshQueueRun]);

  const shouldPoll =
    Boolean(selectedClaimId) &&
    isWorkspaceBusy(isRunning, isRunningQueue, claimDetail, claims);

  useEffect(() => {
    if (!shouldPoll || !selectedClaimId) return;
    const timer = window.setInterval(() => {
      void Promise.all([fetchClaimDetail(selectedClaimId), fetchClaims()])
        .then(([detail, queue]) => {
          setClaimDetail(detail);
          setClaims(queue);
        })
        .catch(() => null);
      refreshQueueRun();
    }, 1000);
    return () => {
      window.clearInterval(timer);
    };
  }, [shouldPoll, selectedClaimId, refreshQueueRun]);

  const handleRunAgent = (claimId: string) => {
    setIsRunning(true);
    setErrorMessage(null);
    void triggerClaimAgent(claimId)
      .then(async (updated) => {
        setClaimDetail(updated);
        setClaims(await fetchClaims());
      })
      .catch(() => {
        setErrorMessage(`Failed to run agent on ${claimId}`);
      })
      .finally(() => {
        setIsRunning(false);
      });
  };

  const handleRunAllWaiting = (cap: number) => {
    if (!claims.some((c) => c.status === "waiting")) return;
    setIsRunningQueue(true);
    setErrorMessage(null);
    void triggerQueueRun(cap)
      .then(async (qState) => {
        setTodos(qState.todos);
        setRunSummary(qState.summary);
        setClaims(await fetchClaims());
        if (selectedClaimId) await loadSelectedClaimBundle(selectedClaimId);
      })
      .catch(() => {
        setErrorMessage("Failed while running waiting claims queue");
      })
      .finally(() => {
        setIsRunningQueue(false);
      });
  };

  const handleSignOff = (claimId: string, handlerId: string) => {
    setErrorMessage(null);
    void signOffClaim(claimId, handlerId)
      .then(async (updated) => {
        setClaimDetail(updated);
        setClaims(await fetchClaims());
      })
      .catch(() => {
        setErrorMessage(`Failed to sign off ${claimId}`);
      });
  };

  const handleResetQueue = () => {
    setErrorMessage(null);
    void resetAllClaims()
      .then(async (resetQueue) => {
        setClaims(resetQueue);
        setTodos([]);
        setRunSummary("");
        if (selectedClaimId) await loadSelectedClaimBundle(selectedClaimId);
      })
      .catch(() => {
        setErrorMessage("Failed to reset claims queue");
      });
  };

  return (
    <div className="app-shell">
      <Topbar
        activeTab={activeTab}
        theme={theme}
        onSelectTab={setActiveTab}
        onToggleTheme={() => {
          const nextTheme = theme === "light" ? "dark" : "light";
          setTheme(nextTheme);
          document.documentElement.dataset.theme = nextTheme;
        }}
      />
      {errorMessage ? (
        <div role="alert" className="error-banner">
          {errorMessage}
        </div>
      ) : null}
      <main>
        {activeTab === "workspace" ? (
          <div className="workspace">
            <ClaimsQueue
              claims={claims}
              todos={todos}
              runSummary={runSummary}
              selectedClaimId={selectedClaimId}
              isRunningQueue={isRunningQueue}
              onSelectClaim={(claimId) => {
                setSelectedClaimId(claimId);
                void loadSelectedClaimBundle(claimId);
              }}
              onRunAllWaiting={handleRunAllWaiting}
              onResetQueue={handleResetQueue}
            />
            <ClaimDetail
              claim={claimDetail}
              policy={policyDetail}
              customer={customer}
              handlers={handlers}
              isRunning={isRunning || isRunningQueue}
              onRunAgent={handleRunAgent}
              onSignOff={handleSignOff}
            />
          </div>
        ) : (
          <InstructionsView
            instructions={instructions}
            policyWording={wording}
            claimsManual={manual}
          />
        )}
      </main>
    </div>
  );
}
