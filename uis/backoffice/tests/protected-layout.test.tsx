import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AuthUser } from "@/lib/auth/types";

const layoutMocks = vi.hoisted(() => ({
  getRequestPath: vi.fn(),
  getServerSessionUser: vi.fn(),
  redirect: vi.fn((path: string) => {
    throw new Error(`NEXT_REDIRECT:${path}`);
  }),
}));

vi.mock("next/navigation", () => ({
  redirect: layoutMocks.redirect,
}));

vi.mock("@/lib/server/request-context", () => ({
  getRequestPath: layoutMocks.getRequestPath,
}));

vi.mock("@/lib/auth/session", () => ({
  getServerSessionUser: layoutMocks.getServerSessionUser,
}));

vi.mock("@/lib/auth/context", () => ({
  AuthProvider: ({ children }: { children: ReactNode }) => <div data-testid="auth-provider">{children}</div>,
}));

vi.mock("@/components/auth/RequirePasswordChangeGate", () => ({
  RequirePasswordChangeGate: ({ children }: { children: ReactNode }) => (
    <div data-testid="password-change-gate">{children}</div>
  ),
}));

vi.mock("@/components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div data-testid="app-shell">{children}</div>,
}));

import ProtectedLayout from "@/app/(protected)/layout";

const activeUser: AuthUser = {
  id: "user-1",
  name: "Admin User",
  email: "admin@example.com",
  role: "admin",
  status: "active",
  must_change_password: false,
  created_at: "2026-06-20T00:00:00Z",
  last_login_at: null,
};

describe("ProtectedLayout auth gate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    layoutMocks.getRequestPath.mockResolvedValue("/suppliers");
    layoutMocks.getServerSessionUser.mockResolvedValue(activeUser);
  });

  it("redirects unauthenticated users to login with a safe next path", async () => {
    layoutMocks.getServerSessionUser.mockResolvedValue(null);

    await expect(ProtectedLayout({ children: <div>Protected child</div> })).rejects.toThrow("NEXT_REDIRECT");

    expect(layoutMocks.redirect).toHaveBeenCalledWith("/login?next=%2Fsuppliers");
  });

  it("redirects temporary-password users to the change-password flow", async () => {
    layoutMocks.getServerSessionUser.mockResolvedValue({ ...activeUser, must_change_password: true });

    await expect(ProtectedLayout({ children: <div>Protected child</div> })).rejects.toThrow("NEXT_REDIRECT");

    expect(layoutMocks.redirect).toHaveBeenCalledWith("/account/change-password?next=%2Fsuppliers");
  });

  it("redirects non-admin users away from admin routes", async () => {
    layoutMocks.getRequestPath.mockResolvedValue("/admin/users");
    layoutMocks.getServerSessionUser.mockResolvedValue({ ...activeUser, role: "user" });

    await expect(ProtectedLayout({ children: <div>Admin child</div> })).rejects.toThrow("NEXT_REDIRECT");

    expect(layoutMocks.redirect).toHaveBeenCalledWith("/");
  });

  it("renders protected content for an authorized user", async () => {
    const ui = await ProtectedLayout({ children: <div>Protected child</div> });

    render(ui);

    expect(screen.getByTestId("auth-provider")).toBeInTheDocument();
    expect(screen.getByTestId("password-change-gate")).toBeInTheDocument();
    expect(screen.getByTestId("app-shell")).toBeInTheDocument();
    expect(screen.getByText("Protected child")).toBeInTheDocument();
  });
});
