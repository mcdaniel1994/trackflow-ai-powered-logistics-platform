import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "connection-recovery.spec.ts",
  outputDir: "/private/tmp/trackflow-connection-recovery-results",
  workers: 1,
  timeout: 60_000,
  use: { ...devices["Desktop Chrome"], baseURL: "http://127.0.0.1:3016", trace: "retain-on-failure" },
  webServer: {
    command: "cp -R public .next/standalone/uis/backoffice/ && cp -R .next/static .next/standalone/uis/backoffice/.next/ && node .next/standalone/uis/backoffice/server.js",
    url: "http://127.0.0.1:3016/login",
    env: {
      HOSTNAME: "127.0.0.1",
      PORT: "3016",
      IDENTITY_API_URL: "http://127.0.0.1:18886",
      CENTRAL_API_URL: "http://127.0.0.1:18886",
      AUTH_COOKIE_SECURE: "false",
      PUBLIC_SUPPORT_ENABLED: "false",
    },
    timeout: 60_000,
  },
});
