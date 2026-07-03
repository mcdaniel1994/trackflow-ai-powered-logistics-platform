// @vitest-environment node

import { describe, expect, it } from "vitest";
import { GET } from "@/app/api/health/route";

describe("deployment health route", () => {
  it("returns 200 rather than an authentication redirect", () => {
    const response = GET();
    expect(response.status).toBe(200);
    expect(response.status).not.toBe(307);
  });
});
