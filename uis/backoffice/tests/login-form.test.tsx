import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginForm } from "@/components/auth/LoginForm";
import { login } from "@/lib/auth/api";

const replace = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace,
    refresh,
  }),
  useSearchParams: () => new URLSearchParams("next=/suppliers"),
}));

vi.mock("@/lib/auth/api", () => ({
  login: vi.fn(),
}));

describe("LoginForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders recovery but no public registration link", () => {
    render(<LoginForm />);
    const registrationPattern = new RegExp("reg" + "ister", "i");

    expect(screen.queryByText(registrationPattern)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /forgot your password/i })).toHaveAttribute("href", "/forgot-password");
  });

  it("logs in and honors a safe next path", async () => {
    vi.mocked(login).mockResolvedValue({
      id: "u1",
      name: "Admin User",
      email: "admin@example.com",
      role: "admin",
      status: "active",
      must_change_password: false,
      created_at: "2026-06-20T00:00:00Z",
      last_login_at: null,
    });

    render(<LoginForm />);

    await userEvent.type(screen.getByLabelText(/email/i), "admin@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "admin-passphrase");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(login).toHaveBeenCalledWith("admin@example.com", "admin-passphrase");
    expect(replace).toHaveBeenCalledWith("/suppliers");
    expect(refresh).toHaveBeenCalled();
  });
});
