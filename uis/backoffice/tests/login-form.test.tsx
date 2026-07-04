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
    expect(screen.getByRole("button", { name: /admin demo/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /employee demo/i })).toBeInTheDocument();
  });

  it("autofills each demo account while keeping the password masked", async () => {
    const user = userEvent.setup();
    render(<LoginForm />);

    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);

    await user.click(screen.getByRole("button", { name: /admin demo/i }));
    expect(emailInput).toHaveValue("corymcdaniel01@gmail.com");
    expect(passwordInput).toHaveValue("password123");
    expect(passwordInput).toHaveAttribute("type", "password");
    expect(screen.getByRole("status")).toHaveTextContent(/admin demo credentials filled in/i);

    await user.click(screen.getByRole("button", { name: /employee demo/i }));
    expect(emailInput).toHaveValue("employee@trackflow.com");
    expect(passwordInput).toHaveValue("password123");
    expect(passwordInput).toHaveAttribute("type", "password");
    expect(screen.getByRole("status")).toHaveTextContent(/employee demo credentials filled in/i);
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
