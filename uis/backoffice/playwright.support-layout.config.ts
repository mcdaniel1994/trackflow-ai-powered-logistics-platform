import { defineConfig, devices } from "@playwright/test";

// Uses the running local website preview; it never starts or contacts a live AI service.
export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "support-layout.spec.ts",
  outputDir: "/private/tmp/trackflow-support-layout-results",
  workers: 1,
  use: { ...devices["Desktop Chrome"], trace: "retain-on-failure" },
});
