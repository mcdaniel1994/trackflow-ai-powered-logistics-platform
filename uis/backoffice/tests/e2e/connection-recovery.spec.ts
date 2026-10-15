import { createServer, type Server } from "node:http";
import { expect, test } from "@playwright/test";

// Local-only Identity and Central API fixtures; the real built app and BFF handle every read.
let sandbox: Server;
let dispatchAttempts = 0;
let receivingFails = false;
let refreshed = false;
let refreshCalls = 0;
const requestedRanges: string[] = [];
test.beforeAll(async () => {
  sandbox = createServer(async (request, response) => {
    const url = new URL(request.url!, "http://127.0.0.1:18886");
    const path = url.pathname;
    response.setHeader("Content-Type", "application/json");
    const user = { id: "local-owner", name: "Local Owner", email: "owner@example.com", role: "admin", status: "active", jurisdiction: "US", must_change_password: false, created_at: "2026-10-15T00:00:00Z", last_login_at: null };
    if (path === "/auth/login") {
      for await (const part of request) void part;
      response.setHeader("Set-Cookie", [
        "trackflow_access=local-test; Path=/; HttpOnly; SameSite=Lax",
        "trackflow_refresh=local-refresh; Path=/; HttpOnly; SameSite=Lax",
        "trackflow_csrf=local-csrf; Path=/; SameSite=Lax",
      ]);
      response.end(JSON.stringify(user));
    } else if (path === "/auth/me" && request.headers.cookie?.includes("trackflow_access=local-test")) {
      response.end(JSON.stringify(user));
    } else if (path === "/auth/refresh") {
      refreshed = true;
      refreshCalls++;
      response.end(JSON.stringify({ ok: true }));
    } else if (path === "/telemetry/metrics/dispatch") {
      dispatchAttempts++;
      requestedRanges.push(url.search);
      if (dispatchAttempts === 1) {
        response.statusCode = 503;
        response.end(JSON.stringify({ detail: "Unavailable" }));
      } else {
        response.end(JSON.stringify({ period: { from: url.searchParams.get("from"), to: url.searchParams.get("to") }, rows: [{ date: "2026-10-15", warehouse: "LA", dispatched: 12 }] }));
      }
    } else if (path === "/telemetry/metrics/receiving") {
      response.statusCode = receivingFails ? 503 : 200;
      response.end(JSON.stringify(receivingFails ? { detail: "Unavailable" } : { rows: [{ date: "2026-10-15", warehouse: "ZGZ", count: 7 }] }));
    } else if (path === "/telemetry/metrics/stock-loss") {
      // Prove authentication refresh still occurs before the resource's transient retry policy.
      response.statusCode = refreshed ? 200 : 401;
      response.end(JSON.stringify(refreshed ? { rows: [] } : { detail: "Unauthenticated" }));
    } else if (path === "/inventory/orders") {
      response.end(JSON.stringify({ items: [], total: 0, limit: 8, offset: 0 }));
    } else {
      response.statusCode = 404;
      response.end(JSON.stringify({ detail: "Fixture route unavailable" }));
    }
  });
  await new Promise<void>((resolve) => sandbox.listen(18886, "127.0.0.1", resolve));
});
test.afterAll(async () => {
  await new Promise<void>((resolve, reject) => sandbox.close((error) => error ? reject(error) : resolve()));
});

test("fresh login renders partial data, recovers automatically, retains stale values and clears changed ranges", async ({ page }) => {
  await page.clock.install();
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill("owner@example.com");
  await page.getByLabel("Password", { exact: true }).fill("local-test-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Operations Overview" })).toBeVisible();
  const dispatchCard = page.getByRole("article").filter({ hasText: "Dispatched (7d)" });
  await expect(page.getByRole("article").filter({ hasText: "Received (7d)" }).getByText("7", { exact: true })).toBeVisible();
  await expect(dispatchCard.getByText("—", { exact: true })).toBeVisible();
  await expect(page.getByRole("status")).toHaveText("Partial data · retrying");
  await page.screenshot({ path: "/private/tmp/trackflow-connection-partial.png", fullPage: true });
  await expect(dispatchCard.getByText("12", { exact: true })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("status")).toHaveText("Live");
  expect(dispatchAttempts).toBe(2);
  expect(refreshCalls).toBe(1);
  await expect(page.getByText("No recent movements yet.")).toBeVisible();

  await page.getByRole("link", { name: "Fulfilment details" }).click();
  await expect(page.getByRole("heading", { name: "Dispatch by day and warehouse" })).toBeVisible();
  await expect(page.getByRole("status")).toHaveText("Live");
  // Speed up the 20-second poll using Playwright's clock; network requests remain real local I/O.
  receivingFails = true;
  await page.clock.runFor(20_000);
  await expect(page.getByRole("alert").filter({ hasText: "Receiving:" })).toBeVisible();
  await expect(page.getByText(/Stale — last successful update/)).toBeVisible();
  await expect(page.getByRole("article").filter({ hasText: "Received (exact)" }).getByText("7", { exact: true })).toBeVisible();
  await expect(page.getByRole("status")).toHaveText("Partial data · retrying");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "/private/tmp/trackflow-connection-stale-mobile.png", fullPage: true });
  receivingFails = false;
  await page.clock.runFor(2_500);
  await expect(page.getByRole("status")).toHaveText("Live");
  await expect(page.getByRole("alert").filter({ hasText: "Receiving:" })).toHaveCount(0);

  // Hold the next range's reads to inspect the immediate clearing of successful old data.
  await page.route("**/api/telemetry/metrics/*?**", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 500));
    await route.continue();
  });
  await page.getByLabel("From", { exact: true }).fill("2026-10-01");
  await page.getByLabel("To", { exact: true }).fill("2026-10-07");
  await page.getByRole("button", { name: "Apply" }).click();
  await expect(page.getByRole("article").getByText("—", { exact: true })).toHaveCount(2);
  await expect(page.getByRole("heading", { name: "Dispatch by day and warehouse" })).toHaveCount(0);
  await expect(page.getByRole("status")).toHaveText("Connecting…");
  await expect(page.getByRole("status")).toHaveText("Live");
  expect(requestedRanges.at(-1)).toBe("?from=2026-10-01&to=2026-10-07");
});
