import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdminUsersView } from "@/components/admin/AdminUsersView";
import { AppShell } from "@/components/AppShell";
import { createUser, listUsers } from "@/lib/auth/api";
import type { AuthUser, CreatedUser } from "@/lib/auth/types";

const authMocks = vi.hoisted(() => ({
  logout: vi.fn(),
  pathname: "/admin/users",
}));

vi.mock("next/navigation", () => ({
  usePathname: () => authMocks.pathname,
}));

vi.mock("@/lib/auth/context", () => ({
  useAuth: () => ({
    user: {
      id: "admin-1",
      name: "Cory McDaniel",
      email: "admin@example.com",
      role: "admin",
      status: "active",
      must_change_password: false,
      created_at: "2026-06-20T00:00:00Z",
      last_login_at: "2026-06-20T00:00:00Z",
    },
    setUser: vi.fn(),
    refreshUser: vi.fn(),
    logout: authMocks.logout,
  }),
}));

vi.mock("@/lib/auth/api", () => ({
  createUser: vi.fn(),
  listUsers: vi.fn(),
  revokeUserSessions: vi.fn(),
  updateUserStatus: vi.fn(),
}));

const users: AuthUser[] = [
  {
    id: "admin-1",
    name: "Cory McDaniel",
    email: "admin@example.com",
    role: "admin",
    status: "active",
    must_change_password: false,
    created_at: "2026-06-20T00:00:00Z",
    last_login_at: "2026-06-20T00:00:00Z",
  },
  {
    id: "user-1",
    name: "Hannah McDaniel",
    email: "hannah@example.com",
    role: "user",
    status: "suspended",
    must_change_password: false,
    created_at: "2026-06-20T00:00:00Z",
    last_login_at: "2026-06-20T00:00:00Z",
  },
];

const createdUser: CreatedUser = {
  id: "user-2",
  name: "New Worker",
  email: "new.worker@example.com",
  role: "user",
  status: "active",
  must_change_password: true,
  created_at: "2026-06-20T00:00:00Z",
  last_login_at: null,
  temporary_password: "temporary-passphrase",
  setup_email_sent: true,
};

describe("Back Office responsive layout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authMocks.pathname = "/admin/users";
    vi.mocked(listUsers).mockResolvedValue(users);
  });

  it("opens mobile navigation from a hamburger drawer and closes after navigation", async () => {
    render(
      <AppShell>
        <div>Shell content</div>
      </AppShell>,
    );

    expect(document.getElementById("mobile-backoffice-navigation")).not.toBeInTheDocument();

    const openButton = screen.getByRole("button", { name: /open navigation/i });
    expect(openButton).toHaveAttribute("aria-controls", "mobile-backoffice-navigation");
    expect(openButton).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(openButton);

    const drawer = document.getElementById("mobile-backoffice-navigation");
    expect(drawer).toBeInTheDocument();
    expect(openButton).toHaveAttribute("aria-expanded", "true");

    const drawerNavigation = within(drawer as HTMLElement);
    const drawerList = drawerNavigation.getByRole("list");
    expect(drawerList).toHaveClass("space-y-2");
    expect(drawerList).not.toHaveClass("overflow-x-auto");
    expect(drawerNavigation.getByRole("link", { name: /inventory \+ carriers/i })).toBeInTheDocument();
    expect(drawerNavigation.getByRole("link", { name: /user management/i })).toBeInTheDocument();

    const accountLink = drawerNavigation.getByRole("link", { name: /account/i });
    accountLink.addEventListener("click", (event) => event.preventDefault(), { once: true });
    await userEvent.click(accountLink);
    expect(document.getElementById("mobile-backoffice-navigation")).not.toBeInTheDocument();
  });

  it("uses one Inventory Management sidebar entry across every inventory route", () => {
    authMocks.pathname = "/backoffice/inventory/orders/outbound";

    render(
      <AppShell>
        <div>Inventory content</div>
      </AppShell>,
    );

    const inventoryLink = screen.getByRole("link", { name: "Inventory Management" });
    expect(inventoryLink).toHaveAttribute("href", "/backoffice/inventory/products");
    expect(inventoryLink).toHaveAttribute("aria-current", "page");
    expect(screen.queryByRole("link", { name: "Inventory Products" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Inventory History" })).not.toBeInTheDocument();
  });

  it("keeps user management overflow inside responsive panels", async () => {
    render(<AdminUsersView />);

    expect(await screen.findAllByText("Cory McDaniel")).toHaveLength(2);

    const table = screen.getByRole("table");
    expect(table).toHaveClass("w-full", "table-fixed");
    expect(table).not.toHaveClass("min-w-[56rem]");
    expect(table.parentElement).toHaveClass("hidden", "max-w-full", "md:block");
    expect(table.parentElement).not.toHaveClass("overflow-x-auto");

    const revokeButton = screen.getAllByRole("button", { name: /revoke sessions/i })[0];
    expect(revokeButton).toHaveClass("border", "bg-white", "text-navy");
    const actionGroup = revokeButton.parentElement?.parentElement;
    expect(actionGroup).toHaveClass("flex-wrap", "justify-end", "w-full", "min-w-0");
    expect(actionGroup).not.toHaveClass("max-w-[22rem]");
    expect(actionGroup).not.toHaveClass("min-w-[24rem]");

    const mobileRows = screen.getAllByRole("article");
    expect(mobileRows).toHaveLength(2);
    expect(within(mobileRows[0]).getByRole("button", { name: /revoke sessions/i })).toHaveClass("w-full");
  });

  it("exposes action descriptions through hover and focus tooltips", async () => {
    render(<AdminUsersView />);

    const suspendButton = (await screen.findAllByRole("button", { name: /suspend/i }))[0];
    expect(suspendButton.getAttribute("aria-describedby")).toContain("suspend");
    expect(suspendButton).toHaveAttribute(
      "title",
      "Temporarily blocks login and refresh, revokes active sessions, and can be reversed.",
    );

    const disableButton = screen.getAllByRole("button", { name: /^disable$/i })[0];
    expect(disableButton.getAttribute("aria-describedby")).toContain("disable");
    expect(disableButton).toHaveAttribute(
      "title",
      "Deactivates the account and revokes sessions. This is reversible, not a hard delete.",
    );

    const reactivateButton = screen.getAllByRole("button", { name: /reactivate/i })[0];
    expect(reactivateButton.getAttribute("aria-describedby")).toContain("reactivate");
    expect(reactivateButton).toHaveAttribute("title", "Restores the account to active. The user must sign in again.");

    const revokeButton = screen.getAllByRole("button", { name: /revoke sessions/i })[0];
    expect(revokeButton.getAttribute("aria-describedby")).toContain("revoke");
    expect(revokeButton).toHaveAttribute(
      "title",
      "Keeps the account active but logs the user out everywhere by revoking refresh sessions.",
    );

    expect(screen.getAllByRole("tooltip", { name: /temporarily blocks login/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("tooltip", { name: /deactivates the account/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("tooltip", { name: /restores the account/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("tooltip", { name: /keeps the account active/i }).length).toBeGreaterThan(0);
  });

  it("disables self-lockout actions for the signed-in admin", async () => {
    render(<AdminUsersView />);

    const suspendButtons = await screen.findAllByRole("button", { name: /suspend/i });
    expect(suspendButtons[0]).toBeDisabled();
    expect(suspendButtons[1]).toBeDisabled();

    const disableButtons = screen.getAllByRole("button", { name: /^disable$/i });
    expect(disableButtons[0]).toBeDisabled();
    expect(disableButtons[1]).not.toBeDisabled();
    expect(disableButtons[2]).toBeDisabled();
    expect(disableButtons[3]).not.toBeDisabled();

    expect(screen.getAllByRole("button", { name: /revoke sessions/i })[0]).not.toBeDisabled();
  });

  it("shows account setup email delivery after creating a user", async () => {
    vi.mocked(createUser).mockResolvedValue(createdUser);
    render(<AdminUsersView />);

    await userEvent.type(screen.getByLabelText(/^name$/i), "New Worker");
    await userEvent.type(screen.getByLabelText(/^email$/i), "new.worker@example.com");
    await userEvent.click(screen.getByRole("button", { name: /^create user$/i }));

    expect(createUser).toHaveBeenCalledWith("New Worker", "new.worker@example.com");
    expect(await screen.findByText(/setup email sent to new\.worker@example\.com/i)).toBeInTheDocument();
    expect(screen.getByText("temporary-passphrase")).toBeInTheDocument();
  });

  it("shows the manual fallback when account setup email delivery fails", async () => {
    vi.mocked(createUser).mockResolvedValue({ ...createdUser, setup_email_sent: false });
    render(<AdminUsersView />);

    await userEvent.type(screen.getByLabelText(/^name$/i), "New Worker");
    await userEvent.type(screen.getByLabelText(/^email$/i), "new.worker@example.com");
    await userEvent.click(screen.getByRole("button", { name: /^create user$/i }));

    expect(await screen.findByText(/setup email could not be sent automatically/i)).toBeInTheDocument();
    expect(screen.getByText("temporary-passphrase")).toBeInTheDocument();
  });
});
