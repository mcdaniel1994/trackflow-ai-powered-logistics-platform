import { expect, test } from "@playwright/test";

test("login page excludes public registration and shows recovery", async ({ page }) => {
  const registrationPattern = new RegExp("reg" + "ister", "i");

  await page.goto("/login");

  await expect(page.getByRole("heading", { name: /backoffice sign in/i })).toBeVisible();
  await expect(page.getByRole("link", { name: registrationPattern })).toHaveCount(0);
  await expect(page.getByRole("link", { name: /forgot your password/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /back to trackflow website/i })).toHaveAttribute(
    "href",
    "https://trackflow-ai-powered-logistics-plat.vercel.app",
  );

  await page.getByRole("button", { name: /admin demo/i }).click();
  await expect(page.getByLabel(/email/i)).toHaveValue("corymcdaniel01@gmail.com");
  await expect(page.getByLabel(/password/i)).toHaveValue("password123");
  await expect(page.getByLabel(/password/i)).toHaveAttribute("type", "password");

  await page.getByRole("button", { name: /employee demo/i }).click();
  await expect(page.getByLabel(/email/i)).toHaveValue("employee@trackflow.com");
  await expect(page.getByLabel(/password/i)).toHaveValue("password123");
});

test("login remains usable without input zoom at a mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/login");

  const emailInput = page.getByLabel(/email/i);
  const passwordInput = page.getByLabel(/password/i);

  await expect(page.getByRole("link", { name: /back to trackflow website/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /admin demo/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /employee demo/i })).toBeVisible();
  await expect(emailInput).toHaveCSS("font-size", "16px");
  await expect(passwordInput).toHaveCSS("font-size", "16px");
});

test("protected routes redirect unauthenticated users to login", async ({ page }) => {
  const protectedRoutes = [
    "/backoffice/inventory/products",
    "/backoffice/inventory/orders/inbound",
    "/backoffice/inventory/orders/outbound",
    "/backoffice/inventory/orders",
    "/incidents",
  ];

  for (const route of protectedRoutes) {
    await page.goto(route);
    await expect(page).toHaveURL(`/login?next=${encodeURIComponent(route)}`);
    await expect(page.getByRole("heading", { name: /backoffice sign in/i })).toBeVisible();
  }
});

test("forgot-password page is public and non-enumerating", async ({ page }) => {
  await page.route("**/api/auth/forgot-password", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ message: "If that address is registered, you'll receive a link shortly." }),
    });
  });

  await page.goto("/forgot-password");

  await expect(page).toHaveURL(/\/forgot-password$/);
  await expect(page.getByRole("heading", { name: /reset access/i })).toBeVisible();
  await page.getByLabel(/email/i).fill("worker@example.com");
  await page.getByRole("button", { name: /send reset link/i }).click();
  await expect(page.getByText(/if that address is registered/i)).toBeVisible();
  await expect(page.getByRole("link", { name: /back to sign in/i })).toHaveCount(1);
});

test("reset-password page handles missing and mismatched credentials", async ({ page }) => {
  await page.goto("/reset-password");

  await expect(page).toHaveURL(/\/reset-password$/);
  await expect(page.getByText(/invalid or expired/i)).toBeVisible();
  await expect(page.getByRole("link", { name: /request a new reset link/i })).toBeVisible();

  await page.goto("/reset-password?token=opaque-token");
  await page.getByLabel(/^New password/i).fill("new-safe-passphrase");
  await page.getByLabel(/confirm password/i).fill("different-passphrase");
  await page.getByRole("button", { name: /reset password/i }).click();
  await expect(page.getByText(/passwords must match/i)).toBeVisible();
});

test("reset-password page shows invalid-token recovery and success redirect", async ({ page }) => {
  await page.route("**/api/auth/reset-password", async (route) => {
    await route.fulfill({
      status: 400,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Invalid or expired reset token" }),
    });
  });

  await page.goto("/reset-password?token=expired-token");
  await page.getByLabel(/^New password/i).fill("new-safe-passphrase");
  await page.getByLabel(/confirm password/i).fill("new-safe-passphrase");
  await page.getByRole("button", { name: /reset password/i }).click();
  await expect(page.getByText(/invalid or expired reset token/i)).toBeVisible();
  await expect(page.getByRole("link", { name: /request a new reset link/i })).toBeVisible();

  await page.unroute("**/api/auth/reset-password");
  await page.route("**/api/auth/reset-password", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    });
  });

  await page.goto("/reset-password?token=valid-token");
  await page.getByLabel(/^New password/i).fill("new-safe-passphrase");
  await page.getByLabel(/confirm password/i).fill("new-safe-passphrase");
  await page.getByRole("button", { name: /reset password/i }).click();
  await expect(page).toHaveURL(/\/login\?reset=success$/);
  await expect(page.getByText(/password has been reset/i)).toBeVisible();
});
