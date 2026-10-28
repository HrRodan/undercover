import { expect, test } from "@playwright/test";

test("displays the 25-claim queue, full claim details, steps, over-limit sign-off, and instructions", async ({
  page,
  request,
}) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "UnderCover", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("25 total claims in queue")).toBeVisible();
  await expect(page.getByRole("button", { name: "CLM-1001" })).toBeVisible();
  await expect(page.getByText("Airport hotel, one night")).toBeVisible();
  await expect(
    page.getByText("Meridian Air cancellation notice"),
  ).toBeVisible();
  await expect(page.getByText("UnderCover Premium")).toBeVisible();

  const stepRes = await request.post("/api/claims/CLM-1001/steps", {
    data: { message: "Reading claim CLM-1001 and verifying carrier delay" },
  });
  expect(stepRes.status()).toBe(200);

  const decisionRes = await request.post("/api/claims/CLM-1001/decision", {
    data: {
      decision: "approve",
      payout: 420.0,
      policy_section: "Section 3: Trip Delay",
      reason:
        "Flight MA 611 was canceled due to crew availability for over 6 hours.",
    },
  });
  expect(decisionRes.status()).toBe(200);

  const payRes = await request.post("/api/claims/CLM-1001/pay", {
    data: { amount: 420.0 },
  });
  expect(payRes.status()).toBe(200);

  await page.getByRole("button", { name: "CLM-1001" }).click();
  await expect(
    page.getByText("Reading claim CLM-1001 and verifying carrier delay"),
  ).toBeVisible();
  await expect(page.getByText("Section 3: Trip Delay")).toBeVisible();

  const overLimitDec = await request.post("/api/claims/CLM-1003/decision", {
    data: {
      decision: "approve",
      payout: 3750.0,
      policy_section: "Section 7: Emergency Medical",
      reason:
        "Emergency fracture reduction in Lisbon is covered less $50 deductible.",
    },
  });
  expect(overLimitDec.status()).toBe(200);

  const blockedPay = await request.post("/api/claims/CLM-1003/pay", {
    data: { amount: 3750.0 },
  });
  expect(blockedPay.status()).toBe(409);

  await page.reload();
  await page.getByRole("button", { name: "CLM-1003" }).click();
  await expect(page.getByText(/Handler sign-off required/)).toBeVisible();

  await page
    .getByRole("button", { name: "Sign Off & Release Payment" })
    .click();
  await expect(page.getByText("HND-01")).toBeVisible();

  await page.getByRole("button", { name: "Agent Instructions" }).click();
  await expect(
    page.getByRole("heading", { name: "Agent Instructions" }),
  ).toBeVisible();
  await expect(page.getByText(/You are the UnderCover Agent/)).toBeVisible();
});
