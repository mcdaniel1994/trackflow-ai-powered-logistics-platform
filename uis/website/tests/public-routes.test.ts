// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { POST as apply } from "@/app/api/careers/applications/route";
import { POST as support } from "@/app/api/support/query/route";
import { sameOrigin } from "@/lib/server/public-http";

const application = {
  full_name: "Alex Demo",
  email: "alex@example.com",
  role: "general",
  experience_years: 3,
  demo_acknowledged: true,
};
const req = (
  body: unknown,
  path = "/api/careers/applications",
  origin = "https://website.example",
) =>
  new Request(`https://website.example${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Origin: origin,
      Cookie: "private-staff-cookie",
    },
    body: JSON.stringify(body),
  });
describe("public routes", () => {
  beforeEach(() => {
    vi.stubEnv("CAREERS_DEMO_ENABLED", "true");
    vi.stubEnv("PUBLIC_SUPPORT_ENABLED", "true");
    vi.stubEnv("WEBSITE_GATEWAY_SECRET", "server-only-secret");
    vi.stubEnv("SUPPORT_GATEWAY_URL", "https://backoffice.example");
    vi.stubEnv("TALENT_API_URL", "https://sandbox.example/api");
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });
  it("reports a disabled support feature without calling the gateway", async () => {
    vi.stubEnv("PUBLIC_SUPPORT_ENABLED", "false");
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const response = await support(
      req(
        { question: "Returns?", language: "en", policy_country: "US" },
        "/api/support/query",
      ),
    );
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ code: "not_enabled" });
    expect(fetch).not.toHaveBeenCalled();
  });
  it.each([
    { full_name: " " },
    { role: "arbitrary_role" },
    { experience_years: -1 },
    { experience_years: 3.5 },
    { experience_years: 61 },
    { demo_acknowledged: false },
  ])(
    "rejects invalid demo fields before the sandbox call: %j",
    async (fields) => {
      const fetch = vi.fn();
      vi.stubGlobal("fetch", fetch);
      expect((await apply(req({ ...application, ...fields }))).status).toBe(
        422,
      );
      expect(fetch).not.toHaveBeenCalled();
    },
  );
  it("rejects malformed/oversized bodies and unconfirmed sandbox defaults", async () => {
    const fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "record-1",
          status: "selected",
          stage: "review",
          applied_at: "2026-10-13",
        }),
        { status: 201 },
      ),
    );
    vi.stubGlobal("fetch", fetch);
    expect((await apply(req(null))).status).toBe(400);
    expect(
      (await apply(req({ ...application, full_name: "a".repeat(20000) })))
        .status,
    ).toBe(400);
    expect(fetch).not.toHaveBeenCalled();
    expect(await (await apply(req(application))).json()).toEqual({
      code: "uncertain",
    });
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("checks the browser host when Next normalizes the internal request URL", () => {
    expect(
      sameOrigin(
        new Request("http://localhost:3005/api/careers/applications", {
          headers: { host: "127.0.0.1:3005", origin: "http://127.0.0.1:3005" },
        }),
      ),
    ).toBe(true);
    expect(
      sameOrigin(
        new Request("http://localhost:3005/api/careers/applications", {
          headers: {
            host: "127.0.0.1:3005",
            origin: "http://foreign.example",
            "x-forwarded-host": "foreign.example",
          },
        }),
      ),
    ).toBe(false);
  });
  it("validates careers fields and blocks foreign origins and disabled configuration", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    expect(
      (await apply(req({ ...application, email: "real@other.com" }))).status,
    ).toBe(422);
    expect(
      (await apply(req({ ...application, status: "selected" }))).status,
    ).toBe(422);
    expect(
      (await apply(req(application, undefined, "https://foreign.example")))
        .status,
    ).toBe(403);
    vi.stubEnv("CAREERS_DEMO_ENABLED", "false");
    expect((await apply(req(application))).status).toBe(503);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("maps a demo into a received pending sandbox record and returns only its ID", async () => {
    const fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "record-1",
          status: "received",
          stage: "pending",
          applied_at: "2026-10-13T00:00:00Z",
          email: "secret@real.test",
        }),
        { status: 201 },
      ),
    );
    vi.stubGlobal("fetch", fetch);
    const response = await apply(req(application));
    expect(response.status).toBe(201);
    expect(await response.json()).toEqual({ candidate_id: "record-1" });
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe("https://sandbox.example/api/records");
    expect(JSON.parse(options.body)).toMatchObject({
      phone: "+1-202-555-0100",
      cv_url: "",
      linkedin_url: "",
      position: "General application",
    });
    expect(JSON.parse(options.body)).not.toHaveProperty("applied_at");
    expect(JSON.parse(options.body)).not.toHaveProperty("status");
    expect(options.headers.Cookie).toBeUndefined();
  });
  it("does not retry writes or claim success without an upstream confirmation", async () => {
    const fetch = vi
      .fn()
      .mockRejectedValue(
        Object.assign(new Error("secret payload"), { name: "TimeoutError" }),
      );
    vi.stubGlobal("fetch", fetch);
    const response = await apply(req(application));
    expect(response.status).toBe(504);
    expect(await response.json()).toEqual({ code: "uncertain" });
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("scrubs upstream errors and malformed confirmations", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response("private details", { status: 500 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "../../escape" }), { status: 201 }),
      );
    vi.stubGlobal("fetch", fetch);
    expect(await (await apply(req(application))).json()).toEqual({
      code: "uncertain",
    });
    expect(await (await apply(req(application))).json()).toEqual({
      code: "uncertain",
    });
  });
  it("relays support through the fixed server-authenticated gateway without staff cookies", async () => {
    const fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          answer: "Public policy answer",
          outcome: "answered",
          trace: "private",
        }),
      ),
    );
    vi.stubGlobal("fetch", fetch);
    const response = await support(
      req(
        {
          question: "Returns?",
          language: "en",
          policy_country: "US",
          recent_context: [],
        },
        "/api/support/query",
      ),
    );
    expect(await response.json()).toEqual({
      answer: "Public policy answer",
      outcome: "answered",
      contact_path: "/#contact",
    });
    expect(fetch.mock.calls[0][0]).toBe(
      "https://backoffice.example/api/public-support/query",
    );
    expect(fetch.mock.calls[0][1].headers).toEqual({
      "Content-Type": "application/json",
      "x-website-gateway-secret": "server-only-secret",
    });
  });
  it("fails closed without gateway configuration and sanitizes rate-limit errors", async () => {
    vi.stubEnv("WEBSITE_GATEWAY_SECRET", "");
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    expect((await support(req({}, "/api/support/query"))).status).toBe(503);
    expect(fetch).not.toHaveBeenCalled();
    vi.stubEnv("WEBSITE_GATEWAY_SECRET", "secret");
    fetch.mockResolvedValue(new Response("private", { status: 429 }));
    const response = await support(req({}, "/api/support/query"));
    expect(response.status).toBe(429);
    expect(await response.json()).toEqual({ code: "busy" });
  });
});
