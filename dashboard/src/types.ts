export type ClaimStatus =
  "waiting" | "in_progress" | "waiting_for_sign_off" | "decided";

export type ClaimDecision = "approve" | "decline" | "refer";

export type PaymentStatus = "unpaid" | "pending_sign_off" | "paid";

export interface ClaimItem {
  description: string;
  category: string;
  amount: number;
}

export interface ClaimDocument {
  name: string;
  type: string;
  content: string;
}

export interface ClaimStep {
  step_number: number;
  message: string;
  created_at: string;
}

export interface ClaimSummary {
  claim_id: string;
  policy_id: string;
  customer_id: string;
  claim_type: string;
  submitted_on: string;
  incident_date: string;
  incident_location: string;
  summary: string;
  amount_claimed: number;
  status: ClaimStatus;
  decision: ClaimDecision | null;
  payout: number | null;
  policy_section: string | null;
  reason: string | null;
  payment_status: PaymentStatus;
  amount_paid: number;
  signed_off_by: string | null;
}

export interface ClaimDetail extends ClaimSummary {
  story: string;
  items: ClaimItem[];
  documents: ClaimDocument[];
  steps: ClaimStep[];
}

export interface PlanDetails {
  plan: string;
  name: string;
  trip_cancellation_max: number;
  trip_delay_waiting_hours: number;
  trip_delay_max: number;
  baggage_delay_waiting_hours: number;
  baggage_delay_max: number;
  baggage_max: number;
  per_item_limit: number;
  passport_max: number;
  emergency_medical_max: number;
  deductible: number;
  deductible_applies_to: string[];
}

export interface AddOnDetails {
  add_on: string;
  name: string;
  effect: string;
  electronics_per_item_limit: number | null;
}

export interface TripDetails {
  destination: string;
  departs_on: string;
  returns_on: string;
  trip_cost: number;
}

export interface PolicyDetail {
  policy_id: string;
  customer_id: string;
  plan: string;
  add_ons: string[];
  purchased_on: string;
  sold_through: string;
  trip: TripDetails;
  travelers: string[];
  status: string;
  plan_details: PlanDetails;
  add_on_details: AddOnDetails[];
}

export interface AddressDetails {
  street: string;
  city: string;
  state: string;
  zip: string;
}

export interface PreviousClaim {
  claim_id: string;
  filed_on: string;
  incident_date: string;
  claim_type: string;
  summary: string;
  outcome: string;
  amount_paid: number;
}

export interface CustomerDetail {
  customer_id: string;
  name: string;
  email: string;
  phone: string;
  date_of_birth: string;
  address: AddressDetails;
  customer_since: string;
  previous_claims: PreviousClaim[];
}

export interface HandlerDetail {
  handler_id: string;
  name: string;
  role: string;
  email: string;
  can_approve_over_limit: boolean;
}

export interface PolicyWordingResponse {
  version: string;
  content: string;
}

export interface InstructionsResponse {
  instructions: string;
}
