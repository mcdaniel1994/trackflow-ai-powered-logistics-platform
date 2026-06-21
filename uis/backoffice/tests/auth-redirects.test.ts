import { describe, expect, it } from "vitest";
import { loginPathFor, safeNextPath } from "@/lib/auth/redirects";

describe("auth redirects", () => {
  it("keeps only same-origin app paths as next destinations", () => {
    expect(safeNextPath("/suppliers")).toBe("/suppliers");
    expect(safeNextPath("/admin/users?status=active")).toBe("/admin/users?status=active");
    expect(safeNextPath("https://evil.example")).toBe("/");
    expect(safeNextPath("//evil.example")).toBe("/");
    expect(safeNextPath("/api/users")).toBe("/");
    expect(safeNextPath("/login")).toBe("/");
    expect(safeNextPath("/forgot-password")).toBe("/");
    expect(safeNextPath("/reset-password?token=abc")).toBe("/");
  });

  it("builds login paths without open redirects", () => {
    expect(loginPathFor("/talent/123")).toBe("/login?next=%2Ftalent%2F123");
    expect(loginPathFor("https://evil.example")).toBe("/login");
  });
});
