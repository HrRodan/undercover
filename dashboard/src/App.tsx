import { useCallback, useEffect, useState } from "react";
import {
  fetchClaimDetail,
  fetchClaims,
  fetchCustomerDetail,
  fetchHandlers,
  fetchInstructions,
  fetchPolicyDetail,
  fetchPolicyWording,
  signOffClaim,
  triggerClaimAgent,
} from "./api";
import { ClaimDetail } from "./components/ClaimDetail";
import { ClaimsQueue } from "./components/ClaimsQueue";
import { InstructionsView } from "./components/InstructionsView";
import type {
  ClaimDetail as ClaimDetailModel,
  ClaimSummary,
  CustomerDetail,
  HandlerDetail,
  PolicyDetail,
  PolicyWordingResponse,
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

export function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("workspace");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [claims, setClaims] = useState<ClaimSummary[]>([]);
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);
  const [claimDetail, setClaimDetail] = useState<ClaimDetailModel | null>(null);
  const [policyDetail, setPolicyDetail] = useState<PolicyDetail | null>(null);
  const [customerDetail, setCustomerDetail] = useState<CustomerDetail | null>(
    null,
  );
  const [handlers, setHandlers] = useState<HandlerDetail[]>([]);
  const [instructions, setInstructions] = useState<string>("");
  const [policyWording, setPolicyWording] =
    useState<PolicyWordingResponse | null>(null);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [isRunningQueue, setIsRunningQueue] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadSelectedClaimBundle = useCallback(async (claimId: string) => {
    try {
      const detail = await fetchClaimDetail(claimId);
      setClaimDetail(detail);
      const [policy, customer] = await Promise.all([
        fetchPolicyDetail(detail.policy_id),
        fetchCustomerDetail(detail.customer_id),
      ]);
      setPolicyDetail(policy);
      setCustomerDetail(customer);
    } catch {
      setErrorMessage(`Unable to load claim ${claimId}`);
    }
  }, []);

  useEffect(() => {
    async function bootstrap() {
      try {
        const [claimsData, handlersData, instructionsData, wordingData] =
          await Promise.all([
            fetchClaims(),
            fetchHandlers(),
            fetchInstructions(),
            fetchPolicyWording(),
          ]);
        setClaims(claimsData);
        setHandlers(handlersData);
        setInstructions(instructionsData.instructions);
        setPolicyWording(wordingData);
        if (claimsData.length > 0) {
          setSelectedClaimId(claimsData[0].claim_id);
          await loadSelectedClaimBundle(claimsData[0].claim_id);
        }
      } catch {
        setErrorMessage("Backend unavailable");
      }
    }
    void bootstrap();
  }, [loadSelectedClaimBundle]);

  const handleSelectClaim = (claimId: string) => {
    setSelectedClaimId(claimId);
    void loadSelectedClaimBundle(claimId);
  };

  const shouldPoll =
    Boolean(selectedClaimId) &&
    (isRunning || isRunningQueue || claimDetail?.status === "in_progress");

  useEffect(() => {
    if (!shouldPoll || !selectedClaimId) return;
    const timer = window.setInterval(() => {
      void Promise.all([fetchClaimDetail(selectedClaimId), fetchClaims()]).then(
        ([detail, queue]) => {
          setClaimDetail(detail);
          setClaims(queue);
        },
      );
    }, 1000);
    return () => {
      window.clearInterval(timer);
    };
  }, [shouldPoll, selectedClaimId]);

  const handleToggleTheme = () => {
    const nextTheme = theme === "light" ? "dark" : "light";
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
  };

  const handleRunAgent = (claimId: string) => {
    setIsRunning(true);
    setErrorMessage(null);
    void triggerClaimAgent(claimId)
      .then(async (updated) => {
        setClaimDetail(updated);
        const refreshedQueue = await fetchClaims();
        setClaims(refreshedQueue);
      })
      .catch(() => {
        setErrorMessage(`Failed to run agent on ${claimId}`);
      })
      .finally(() => {
        setIsRunning(false);
      });
  };

  const handleRunAllWaiting = () => {
    const waitingIds = claims
      .filter((c) => c.status === "waiting")
      .map((c) => c.claim_id);
    if (waitingIds.length === 0) return;
    setIsRunningQueue(true);
    setErrorMessage(null);
    async function processQueue() {
      try {
        for (const claimId of waitingIds) {
          setSelectedClaimId(claimId);
          await loadSelectedClaimBundle(claimId);
          const updated = await triggerClaimAgent(claimId);
          setClaimDetail(updated);
          setClaims(await fetchClaims());
        }
      } catch {
        setErrorMessage("Failed while running waiting claims queue");
      } finally {
        setIsRunningQueue(false);
      }
    }
    void processQueue();
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

  return (
    <div className="app-shell">
      <Topbar
        activeTab={activeTab}
        theme={theme}
        onSelectTab={setActiveTab}
        onToggleTheme={handleToggleTheme}
      />
      {errorMessage ? (
        <div
          role="alert"
          style={{ padding: "12px 24px", color: "var(--rose-text)" }}
        >
          {errorMessage}
        </div>
      ) : null}
      <main>
        {activeTab === "workspace" ? (
          <div className="workspace">
            <ClaimsQueue
              claims={claims}
              selectedClaimId={selectedClaimId}
              isRunningQueue={isRunningQueue}
              onSelectClaim={handleSelectClaim}
              onRunAllWaiting={handleRunAllWaiting}
            />
            <ClaimDetail
              claim={claimDetail}
              policy={policyDetail}
              customer={customerDetail}
              handlers={handlers}
              isRunning={isRunning || isRunningQueue}
              onRunAgent={handleRunAgent}
              onSignOff={handleSignOff}
            />
          </div>
        ) : (
          <InstructionsView
            instructions={instructions}
            policyWording={policyWording}
          />
        )}
      </main>
    </div>
  );
}
