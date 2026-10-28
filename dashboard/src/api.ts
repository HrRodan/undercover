import type {
  ClaimDetail,
  ClaimSummary,
  CustomerDetail,
  HandlerDetail,
  InstructionsResponse,
  PolicyDetail,
  PolicyWordingResponse,
} from "./types";

const USD_FORMATTER = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

export function formatUsd(amount: number): string {
  return USD_FORMATTER.format(amount);
}

export function formatClaimType(claimType: string): string {
  return claimType
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(`HTTP ${String(response.status)} for ${url}`);
  }
  return (await response.json()) as T;
}

export async function fetchClaims(): Promise<ClaimSummary[]> {
  return requestJson<ClaimSummary[]>("/api/claims");
}

export async function fetchClaimDetail(claimId: string): Promise<ClaimDetail> {
  return requestJson<ClaimDetail>(`/api/claims/${claimId}`);
}

export async function fetchPolicyDetail(
  policyId: string,
): Promise<PolicyDetail> {
  return requestJson<PolicyDetail>(`/api/policies/${policyId}`);
}

export async function fetchCustomerDetail(
  customerId: string,
): Promise<CustomerDetail> {
  return requestJson<CustomerDetail>(`/api/customers/${customerId}`);
}

export async function fetchHandlers(): Promise<HandlerDetail[]> {
  return requestJson<HandlerDetail[]>("/api/handlers");
}

export async function fetchInstructions(): Promise<InstructionsResponse> {
  return requestJson<InstructionsResponse>("/api/instructions");
}

export async function fetchPolicyWording(): Promise<PolicyWordingResponse> {
  return requestJson<PolicyWordingResponse>("/api/policy-wording");
}

export async function triggerClaimAgent(claimId: string): Promise<ClaimDetail> {
  return requestJson<ClaimDetail>(`/api/claims/${claimId}/run`, {
    method: "POST",
  });
}

export async function signOffClaim(
  claimId: string,
  handlerId: string,
): Promise<ClaimDetail> {
  return requestJson<ClaimDetail>(`/api/claims/${claimId}/sign-off`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ handler_id: handlerId }),
  });
}
