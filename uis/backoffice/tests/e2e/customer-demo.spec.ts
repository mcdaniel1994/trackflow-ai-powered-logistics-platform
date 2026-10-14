import { createServer, type Server } from "node:http";
import { expect, test } from "@playwright/test";

// Disposable upstreams exercise the real website/BFF routes without live accounts or writes.
let sandbox: Server;
let candidate: Record<string, unknown> | undefined;
const notes: Array<Record<string, unknown>> = [];
let creates = 0;
test.beforeAll(async () => {
  sandbox = createServer(async (request, response) => {
    const path = new URL(request.url!, "http://127.0.0.1:18884").pathname;
    const parts: Buffer[] = [];
    for await (const part of request) parts.push(Buffer.from(part));
    const body = parts.length
      ? JSON.parse(Buffer.concat(parts).toString())
      : {};
    response.setHeader("Content-Type", "application/json");
    const user = {
      id: "demo-owner",
      name: "Demo Owner",
      email: "owner@example.com",
      role: "admin",
      status: "active",
      jurisdiction: "US",
      must_change_password: false,
      created_at: "2026-10-13T00:00:00Z",
      last_login_at: null,
    };
    if (path === "/auth/login" && request.method === "POST") {
      response.setHeader("Set-Cookie", [
        "trackflow_access=local-test; Path=/; HttpOnly; SameSite=Lax",
        "trackflow_refresh=local-refresh; Path=/; HttpOnly; SameSite=Lax",
        "trackflow_csrf=local-csrf; Path=/; SameSite=Lax",
      ]);
      response.end(JSON.stringify(user));
    } else if (
      path === "/auth/me" &&
      request.headers.cookie?.includes("trackflow_access=local-test")
    ) {
      response.end(JSON.stringify(user));
    } else if (path === "/records" && request.method === "POST") {
      creates++;
      candidate = {
        ...body,
        id: "demo-candidate-42",
        status: "received",
        stage: "pending",
        applied_at: new Date().toISOString(),
      };
      response.statusCode = 201;
      response.end(JSON.stringify(candidate));
    } else if (path === "/records/demo-candidate-42/notes") {
      if (request.method === "POST") {
        const note = {
          ...body,
          id: "demo-note-1",
          created_at: new Date().toISOString(),
        };
        notes.push(note);
        response.statusCode = 201;
        response.end(JSON.stringify(note));
      } else response.end(JSON.stringify({ data: notes }));
    } else if (path === "/records/demo-candidate-42" && candidate) {
      if (request.method === "PATCH") candidate = { ...candidate, ...body };
      response.end(JSON.stringify(candidate));
    } else if (path === "/records") {
      response.end(
        JSON.stringify({
          data: candidate ? [candidate] : [],
          total: candidate ? 1 : 0,
        }),
      );
    } else {
      response.statusCode = 401;
      response.end(JSON.stringify({ detail: "Not authenticated" }));
    }
  });
  await new Promise<void>((resolve) =>
    sandbox.listen(18884, "127.0.0.1", resolve),
  );
});
test.afterAll(async () => {
  await new Promise<void>((resolve, reject) =>
    sandbox.close((error) => (error ? reject(error) : resolve())),
  );
});

test("fictional application reaches the authenticated talent record, stage and notes", async ({
  page,
}) => {
  await page.goto("http://127.0.0.1:3005/careers");
  await expect(page).toHaveTitle(/Careers/);
  await expect(page.locator('meta[property="og:image"]')).toHaveAttribute("content", /trackflow-operations-hero\.png$/);
  await expect(page.locator('meta[name="twitter:image"]')).toHaveAttribute("content", /trackflow-operations-hero\.png$/);
  expect(
    (
      await page.locator('script[type="application/ld+json"]').allTextContents()
    ).join(" "),
  ).not.toContain("JobPosting");
  await page
    .getByRole("article")
    .filter({
      has: page.getByRole("heading", {
        name: "Warehouse Associate — Los Angeles",
      }),
    })
    .getByRole("button")
    .click();
  await page.getByRole("button", { name: "Fill sample application" }).click();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "/private/tmp/trackflow-careers-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Submit demo application" }).click();
  await expect(
    page.getByRole("heading", { name: "Demo application received" }),
  ).toBeVisible();
  expect(creates).toBe(1);
  expect(candidate).toMatchObject({
    status: "received",
    stage: "pending",
    position: "Warehouse Associate — Los Angeles",
    phone: "+1-202-555-0100",
    linkedin_url: "",
    cv_url: "",
  });
  expect(String(candidate?.email)).toMatch(/@example\.com$/);
  expect(new Date(String(candidate?.applied_at)).getTime()).toBeGreaterThan(
    Date.now() - 60_000,
  );
  await page.getByRole("link", { name: "View in Back Office" }).click();
  await expect(page).toHaveURL(/\/login\?next=/);
  await expect(async () => {
    await page.getByRole("button", { name: /admin demo/i }).click();
    await expect(page.getByLabel("Email", { exact: true })).not.toHaveValue("");
  }).toPass({ timeout: 20_000 });
  await page.getByLabel("Email", { exact: true }).fill("owner@example.com");
  await page
    .getByLabel("Password", { exact: true })
    .fill("local-test-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(
    "http://127.0.0.1:3006/talent/demo-candidate-42",
  );
  await expect(page.getByRole("heading", { name: "Alex Demo" })).toBeVisible();
  await page.locator("#detail-stage").selectOption("review");
  await expect(page.getByText("Stage updated.", { exact: true })).toBeVisible();
  await page
    .getByLabel("Add note", { exact: true })
    .fill("Fictional applicant reviewed for portfolio demo.");
  await page.getByRole("button", { name: "Add note", exact: true }).click();
  await expect(page.getByText("Note added.", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.locator("#detail-stage")).toHaveValue("review");
  await expect(
    page.getByText("Fictional applicant reviewed for portfolio demo.", {
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Back to list", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Talent Pipeline", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(
    page.getByRole("row", { name: /Alex Demo.*Warehouse Associate/ }),
  ).toBeVisible();
});

test("mobile public panel preserves focus, separates country and language, and fails safely", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("http://127.0.0.1:3005/careers");
  const launcher = page.getByRole("button", { name: "Chat with TrackFlow" });
  await launcher.click();
  const panel = page.getByRole("dialog", { name: "TrackFlow Support" });
  await expect(panel).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(launcher).toBeFocused();
  await launcher.click();
  await panel.getByRole("combobox").selectOption("ES");
  await panel.getByRole("textbox").fill("What is the return policy?");
  await panel.getByRole("button", { name: "Send", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText(/not been enabled/i);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/private/tmp/trackflow-public-support-mobile.png",
  });
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Switch to Spanish" }).click();
  await expect(
    page.getByRole("heading", { name: "Trabaja en TrackFlow" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Empleo", exact: true }),
  ).toHaveAttribute("href", "/careers");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/private/tmp/trackflow-careers-mobile-spanish.png",
    fullPage: true,
  });
});
