import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { formatClaimType, formatUsd } from "./api";
import type {
  ClaimDetail,
  ClaimSummary,
  CustomerDetail,
  HandlerDetail,
  PolicyDetail,
} from "./types";

const CLAIM_1001_SUMMARY: ClaimSummary = {
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
};

const CLAIM_1003_SUMMARY: ClaimSummary = {
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
  reason: "Covered emergency medical claim less $50 deductible.",
  payment_status: "pending_sign_off",
  amount_paid: 0.0,
  signed_off_by: null,
};

const SAMPLE_CLAIMS: ClaimSummary[] = [CLAIM_1001_SUMMARY, CLAIM_1003_SUMMARY];

const CLAIM_1001_DETAIL: ClaimDetail = {
  ...CLAIM_1001_SUMMARY,
  story: "My flight home from Rome was canceled by Meridian Air.",
  items: [
    {
      description: "Airport hotel, one night",
      category: "accommodation",
      amount: 245.0,
    },
    {
      description: "Dinner and breakfast",
      category: "meals",
      amount: 95.0,
    },
    {
      description: "Taxis",
      category: "transport",
      amount: 80.0,
    },
  ],
  documents: [
    {
      name: "Meridian Air cancellation notice",
      type: "carrier_report",
      content: "Flight MA 611 canceled due to crew availability.",
    },
  ],
  steps: [],
};

const CLAIM_1001_DECIDED: ClaimDetail = {
  ...CLAIM_1001_DETAIL,
  status: "decided",
  decision: "approve",
  payout: 420.0,
  policy_section: "Section 3: Trip Delay",
  reason: "Covered 19-hour delay under Section 3.",
  payment_status: "paid",
  amount_paid: 420.0,
  steps: [
    {
      step_number: 1,
      message: "Reading claim CLM-1001",
      created_at: "2026-06-24T10:00:00Z",
    },
    {
      step_number: 2,
      message: "Recording decision: approve ($420.00)",
      created_at: "2026-06-24T10:00:02Z",
    },
  ],
};

const CLAIM_1003_DETAIL: ClaimDetail = {
  ...CLAIM_1003_SUMMARY,
  story: "I slipped on wet cobblestones in Lisbon and fractured my wrist.",
  items: [
    {
      description: "Emergency room visit and cast",
      category: "medical",
      amount: 3800.0,
    },
  ],
  documents: [
    {
      name: "Hospital itemized bill",
      type: "invoice",
      content: "Hospital Santa Clara total $3,800.00.",
    },
  ],
  steps: [
    {
      step_number: 1,
      message: "Reading claim CLM-1003",
      created_at: "2026-07-06T10:00:00Z",
    },
    {
      step_number: 2,
      message: "Payment of $3,750.00 held pending handler sign-off",
      created_at: "2026-07-06T10:00:03Z",
    },
  ],
};

const CLAIM_1003_SIGNED: ClaimDetail = {
  ...CLAIM_1003_DETAIL,
  status: "decided",
  payment_status: "paid",
  amount_paid: 3750.0,
  signed_off_by: "HND-01",
};

const SAMPLE_POLICY: PolicyDetail = {
  policy_id: "POL-2001",
  customer_id: "CUS-3001",
  plan: "premium",
  add_ons: [],
  purchased_on: "2026-04-22",
  sold_through: "Meridian Air checkout",
  trip: {
    destination: "Rome, Italy",
    departs_on: "2026-06-10",
    returns_on: "2026-06-18",
    trip_cost: 3100.0,
  },
  travelers: ["Maya Patel"],
  status: "active",
  plan_details: {
    plan: "premium",
    name: "UnderCover Premium",
    trip_cancellation_max: 5000.0,
    trip_delay_waiting_hours: 6,
    trip_delay_max: 800.0,
    baggage_delay_waiting_hours: 12,
    baggage_delay_max: 300.0,
    baggage_max: 1500.0,
    per_item_limit: 300.0,
    passport_max: 250.0,
    emergency_medical_max: 100000.0,
    deductible: 50.0,
    deductible_applies_to: ["baggage", "emergency_medical"],
  },
  add_on_details: [],
};

const SAMPLE_CUSTOMER: CustomerDetail = {
  customer_id: "CUS-3001",
  name: "Maya Patel",
  email: "maya.patel@example.com",
  phone: "+1 201 555 0143",
  date_of_birth: "1988-03-14",
  address: {
    street: "48 Wayne Street",
    city: "Jersey City",
    state: "NJ",
    zip: "07302",
  },
  customer_since: "2023-04-11",
  previous_claims: [
    {
      claim_id: "CLM-0412",
      filed_on: "2024-08-19",
      incident_date: "2024-08-09",
      claim_type: "baggage_delay",
      summary: "Checked bag arrived 30 hours late in Lisbon",
      outcome: "approved",
      amount_paid: 140.0,
    },
  ],
};

const SAMPLE_HANDLERS: HandlerDetail[] = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
    email: "dana@undercover.example",
    can_approve_over_limit: true,
  },
  {
    handler_id: "HND-02",
    name: "Marcus Oyelaran",
    role: "Claims Handler",
    email: "marcus@undercover.example",
    can_approve_over_limit: true,
  },
];

const MOCK_ROUTES: Record<string, unknown> = {
  "GET /api/claims": SAMPLE_CLAIMS,
  "GET /api/handlers": SAMPLE_HANDLERS,
  "GET /api/instructions": {
    instructions: "You are the UnderCover Agent. Follow the wording.",
  },
  "GET /api/policy-wording": {
    version: "2026.1",
    content: "# UnderCover Travel Insurance: Policy Wording",
  },
  "GET /api/claims/CLM-1001": CLAIM_1001_DETAIL,
  "POST /api/claims/CLM-1001/run": CLAIM_1001_DECIDED,
  "GET /api/claims/CLM-1003": CLAIM_1003_DETAIL,
  "POST /api/claims/CLM-1003/sign-off": CLAIM_1003_SIGNED,
  "GET /api/policies/POL-2001": SAMPLE_POLICY,
  "GET /api/policies/POL-2003": SAMPLE_POLICY,
  "GET /api/customers/CUS-3001": SAMPLE_CUSTOMER,
  "GET /api/customers/CUS-3003": SAMPLE_CUSTOMER,
};

function createMockFetch() {
  return vi.fn((url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const payload = MOCK_ROUTES[`${method} ${url}`];
    if (payload !== undefined) {
      return Promise.resolve(new Response(JSON.stringify(payload)));
    }
    return Promise.resolve(new Response("Not found", { status: 404 }));
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("loads the queue, displays full claim details, runs the agent, and shows steps", async () => {
  const mockFetch = createMockFetch();
  vi.stubGlobal("fetch", mockFetch);

  render(<App />);

  expect(
    await screen.findByText(/My flight home from Rome was canceled/),
  ).toBeDefined();
  expect(screen.getByText("Airport hotel, one night")).toBeDefined();
  expect(screen.getByText("Meridian Air cancellation notice")).toBeDefined();
  expect(screen.getByText("UnderCover Premium")).toBeDefined();
  expect(screen.getByText(/Maya Patel/)).toBeDefined();
  expect(formatUsd(420)).toBe("$420.00");
  expect(formatClaimType("trip_delay")).toBe("Trip Delay");

  const runAllBtn = screen.getByRole("button", {
    name: "Run All Waiting (1)",
  });
  fireEvent.click(runAllBtn);

  expect(
    await screen.findByText("Recording decision: approve ($420.00)"),
  ).toBeDefined();
  expect(
    screen.getByText("Covered 19-hour delay under Section 3."),
  ).toBeDefined();
  expect(screen.getByText("Section 3: Trip Delay")).toBeDefined();

  const rerunBtn = await screen.findByRole("button", { name: "Rerun Agent" });
  fireEvent.click(rerunBtn);
  expect(
    await screen.findByText("Recording decision: approve ($420.00)"),
  ).toBeDefined();
});

it("allows handler sign-off on a claim over $1,000 and switches to Agent Instructions", async () => {
  const mockFetch = createMockFetch();
  vi.stubGlobal("fetch", mockFetch);

  render(<App />);

  const claim1003Button = await screen.findByRole("button", {
    name: "CLM-1003",
  });
  fireEvent.click(claim1003Button);

  expect(await screen.findByText(/Handler sign-off required/)).toBeDefined();
  expect(
    screen.getByText("Payment of $3,750.00 held pending handler sign-off"),
  ).toBeDefined();

  const handlerSelect = screen.getByLabelText("Handler:");
  fireEvent.change(handlerSelect, { target: { value: "HND-02" } });

  const signOffBtn = screen.getByRole("button", {
    name: "Sign Off & Release Payment",
  });
  fireEvent.click(signOffBtn);

  await waitFor(() => {
    expect(screen.getByText("HND-01")).toBeDefined();
  });

  const instructionsTab = screen.getByRole("button", {
    name: "Agent Instructions",
  });
  fireEvent.click(instructionsTab);

  expect(await screen.findByText(/You are the UnderCover Agent/)).toBeDefined();
  expect(
    screen.getByText(/# UnderCover Travel Insurance: Policy Wording/),
  ).toBeDefined();

  const themeBtn = screen.getByRole("button", { name: "Dark mode" });
  fireEvent.click(themeBtn);
  expect(document.documentElement.dataset.theme).toBe("dark");
});

it("shows an error alert when the backend fails", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<App />);
  expect(await screen.findByRole("alert")).toBeDefined();
});
