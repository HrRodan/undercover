import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import {
  fetchClaimDetail,
  fetchClaims,
  fetchCustomerDetail,
  fetchHandlers,
  fetchInstructions,
  fetchPolicyDetail,
  fetchPolicyWording,
  formatClaimType,
  formatUsd,
  signOffClaim,
  triggerClaimAgent,
} from "./api";
import { ClaimsQueue } from "./components/ClaimsQueue";
import { PaymentStatusBadge } from "./components/StatusBadge";
import type { ClaimSummary } from "./types";

const SAMPLE_CLAIMS: ClaimSummary[] = [
  {
    claim_id: "CLM-1001",
    policy_id: "POL-2001",
    customer_id: "CUS-3001",
    claim_type: "trip_delay",
    submitted_on: "2026-06-24",
    incident_date: "2026-06-18",
    incident_location: "Rome, Italy",
    summary: "Flight home canceled by the airline",
    amount_claimed: 420.0,
    status: "waiting",
    decision: null,
    payout: null,
    policy_section: null,
    reason: null,
    payment_status: "unpaid",
    amount_paid: 0.0,
    signed_off_by: null,
  },
  {
    claim_id: "CLM-1003",
    policy_id: "POL-2003",
    customer_id: "CUS-3003",
    claim_type: "emergency_medical",
    submitted_on: "2026-07-06",
    incident_date: "2026-06-27",
    incident_location: "Lisbon, Portugal",
    summary: "Hospital visit abroad after a fall",
    amount_claimed: 3800.0,
    status: "waiting_for_sign_off",
    decision: "approve",
    payout: 3750.0,
    policy_section: "Section 7: Emergency Medical",
    reason: "Covered medical claim.",
    payment_status: "pending_sign_off",
    amount_paid: 0.0,
    signed_off_by: null,
  },
  {
    claim_id: "CLM-1004",
    policy_id: "POL-2004",
    customer_id: "CUS-3004",
    claim_type: "baggage_delay",
    submitted_on: "2026-07-10",
    incident_date: "2026-07-02",
    incident_location: "Edinburgh, United Kingdom",
    summary: "Checked bag arrived 31 hours late",
    amount_claimed: 186.0,
    status: "decided",
    decision: "decline",
    payout: 0.0,
    policy_section: "Section 4: Baggage Delay",
    reason: "Declined.",
    payment_status: "unpaid",
    amount_paid: 0.0,
    signed_off_by: null,
  },
];

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows that the backend is up", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}")));
  render(<App />);
  expect(await screen.findByText("Backend: up")).toBeDefined();
});

it("shows that the backend is down", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<App />);
  expect(await screen.findByText("Backend: down")).toBeDefined();
});

it("renders ClaimsQueue with USD formatting and filters by status", () => {
  const onSelect = vi.fn();
  render(
    <div>
      <PaymentStatusBadge paymentStatus="paid" />
      <ClaimsQueue
        claims={SAMPLE_CLAIMS}
        selectedClaimId="CLM-1001"
        onSelectClaim={onSelect}
      />
    </div>,
  );

  expect(screen.getByText("$420.00")).toBeDefined();
  expect(screen.getByText("$3,750.00")).toBeDefined();
  expect(formatUsd(1250)).toBe("$1,250.00");
  expect(formatClaimType("trip_delay")).toBe("Trip Delay");

  const filterGroup = screen.getByRole("group", { name: "Filter queue" });
  const signOffBtn = Array.from(filterGroup.querySelectorAll("button")).find(
    (btn) => btn.textContent === "Waiting for sign-off",
  );
  if (!signOffBtn) throw new Error("Missing filter button");
  fireEvent.click(signOffBtn);

  expect(screen.getByText("CLM-1003")).toBeDefined();
  expect(screen.queryByText("CLM-1001")).toBeNull();

  fireEvent.click(screen.getByText("CLM-1003"));
  expect(onSelect).toHaveBeenCalledWith("CLM-1003");
});

it("calls typed api helpers and handles error statuses", async () => {
  const mockFetch = vi
    .fn()
    .mockResolvedValueOnce(new Response(JSON.stringify(SAMPLE_CLAIMS)))
    .mockResolvedValueOnce(new Response(JSON.stringify(SAMPLE_CLAIMS[0])))
    .mockResolvedValueOnce(new Response(JSON.stringify({ policy_id: "POL-1" })))
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ customer_id: "CUS-1" })),
    )
    .mockResolvedValueOnce(new Response(JSON.stringify([])))
    .mockResolvedValueOnce(new Response(JSON.stringify({ instructions: "ok" })))
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ version: "2026.1", content: "wording" })),
    )
    .mockResolvedValueOnce(new Response(JSON.stringify(SAMPLE_CLAIMS[0])))
    .mockResolvedValueOnce(new Response(JSON.stringify(SAMPLE_CLAIMS[1])))
    .mockResolvedValueOnce(new Response("Not found", { status: 404 }));

  vi.stubGlobal("fetch", mockFetch);

  await expect(fetchClaims()).resolves.toHaveLength(3);
  await expect(fetchClaimDetail("CLM-1001")).resolves.toBeDefined();
  await expect(fetchPolicyDetail("POL-2001")).resolves.toBeDefined();
  await expect(fetchCustomerDetail("CUS-3001")).resolves.toBeDefined();
  await expect(fetchHandlers()).resolves.toEqual([]);
  await expect(fetchInstructions()).resolves.toEqual({ instructions: "ok" });
  await expect(fetchPolicyWording()).resolves.toEqual({
    version: "2026.1",
    content: "wording",
  });
  await expect(triggerClaimAgent("CLM-1001")).resolves.toBeDefined();
  await expect(signOffClaim("CLM-1003", "HND-01")).resolves.toBeDefined();
  await expect(fetchClaimDetail("CLM-9999")).rejects.toThrow("HTTP 404");
});
