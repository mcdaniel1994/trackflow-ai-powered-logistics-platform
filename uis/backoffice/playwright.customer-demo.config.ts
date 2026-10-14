import { defineConfig, devices } from "@playwright/test";

const sandbox = "http://127.0.0.1:18884";
export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "customer-demo.spec.ts",
  outputDir: "/private/tmp/trackflow-customer-demo-results",
  workers: 1,
  timeout: 60_000,
  use: { ...devices["Desktop Chrome"], trace: "retain-on-failure" },
  webServer: [
    {
      command:
        "npm run dev --workspace trackflow-website -- --hostname 127.0.0.1 --port 3005",
      url: "http://127.0.0.1:3005/careers",
      env: {
        TALENT_API_URL: sandbox,
        CAREERS_DEMO_ENABLED: "true",
        PUBLIC_SUPPORT_ENABLED: "false",
        NEXT_PUBLIC_BACKOFFICE_URL: "http://127.0.0.1:3006",
      },
      timeout: 120_000,
    },
    {
      command:
        "npm run dev --workspace trackflow-backoffice -- --hostname 127.0.0.1 --port 3006",
      url: "http://127.0.0.1:3006/login",
      env: {
        TALENT_API_URL: sandbox,
        IDENTITY_API_URL: sandbox,
        AUTH_COOKIE_SECURE: "false",
        PUBLIC_SUPPORT_ENABLED: "false",
      },
      timeout: 120_000,
    },
  ],
});
