// @vitest-environment node
import { afterEach, expect, it, vi } from "vitest";
import { POST } from "@/app/api/public-support/query/route";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});
const req = (secret: string) =>
  new Request("https://backoffice.example/api/public-support/query", {
    method: "POST",
    headers: {
      "x-website-gateway-secret": secret,
      Cookie: "staff-cookie",
      Authorization: "Bearer staff-token",
    },
    body: JSON.stringify({ question: "Returns?" }),
  });
it("rejects unauthenticated service calls and missing feature configuration", async () => {
  vi.stubEnv("WEBSITE_GATEWAY_SECRET", "service-secret");
  vi.stubEnv("PUBLIC_SUPPORT_ENABLED", "true");
  expect((await POST(req("wrong"))).status).toBe(403);
  vi.stubEnv("PUBLIC_SUPPORT_ENABLED", "false");
  expect((await POST(req("service-secret"))).status).toBe(503);
});
it("forwards only a fixed public-support operation, no staff identity or trace data", async () => {
  vi.stubEnv("WEBSITE_GATEWAY_SECRET", "service-secret");
  vi.stubEnv("PUBLIC_SUPPORT_ENABLED", "true");
  vi.stubEnv("CENTRAL_API_URL", "http://central-api:8000");
  const fetch = vi
    .fn()
    .mockResolvedValue(
      new Response(
        JSON.stringify({
          answer: "Public answer",
          outcome: "answered",
          trace_id: "private",
        }),
      ),
    );
  vi.stubGlobal("fetch", fetch);
  expect(await (await POST(req("service-secret"))).json()).toEqual({
    answer: "Public answer",
    outcome: "answered",
    contact_path: "/#contact",
  });
  expect(fetch.mock.calls[0][0]).toBe(
    "http://central-api:8000/public-support/query",
  );
  expect(fetch.mock.calls[0][1].headers).toEqual({
    "Content-Type": "application/json",
    "x-website-gateway-secret": "service-secret",
  });
});
