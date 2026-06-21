import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ForgotPasswordForm } from "@/components/auth/ForgotPasswordForm";
import { ResetPasswordForm } from "@/components/auth/ResetPasswordForm";
import { forgotPassword, resetPassword } from "@/lib/auth/api";

const replace = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace,
    refresh,
  }),
}));

vi.mock("@/lib/auth/api", () => ({
  forgotPassword: vi.fn(),
  resetPassword: vi.fn(),
}));

describe("password reset forms", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("submits forgot-password and shows the generic confirmation", async () => {
    vi.mocked(forgotPassword).mockResolvedValue({
      message: "If that address is registered, you'll receive a link shortly.",
    });

    render(<ForgotPasswordForm />);

    await userEvent.type(screen.getByLabelText(/email/i), "worker@example.com");
    await userEvent.click(screen.getByRole("button", { name: /send reset link/i }));

    expect(forgotPassword).toHaveBeenCalledWith("worker@example.com");
    expect(await screen.findByText(/if that address is registered/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /send reset link/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /back to sign in/i })).not.toBeInTheDocument();
  });

  it("blocks reset submit when the token is missing", () => {
    render(<ResetPasswordForm token="" />);

    expect(screen.getByText(/invalid or expired/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /request a new reset link/i })).toHaveAttribute("href", "/forgot-password");
    expect(resetPassword).not.toHaveBeenCalled();
  });

  it("blocks reset submit when passwords do not match", async () => {
    render(<ResetPasswordForm token="opaque-token" />);

    await userEvent.type(screen.getByLabelText(/^new password/i), "new-safe-passphrase");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "different-passphrase");
    await userEvent.click(screen.getByRole("button", { name: /reset password/i }));

    expect(screen.getByText(/passwords must match/i)).toBeInTheDocument();
    expect(resetPassword).not.toHaveBeenCalled();
  });

  it("shows invalid or expired token recovery UX", async () => {
    vi.mocked(resetPassword).mockRejectedValue({ message: "Invalid or expired reset token" });

    render(<ResetPasswordForm token="opaque-token" />);

    await userEvent.type(screen.getByLabelText(/^new password/i), "new-safe-passphrase");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "new-safe-passphrase");
    await userEvent.click(screen.getByRole("button", { name: /reset password/i }));

    expect(await screen.findByText(/invalid or expired reset token/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /request a new reset link/i })).toHaveAttribute("href", "/forgot-password");
  });

  it("redirects to login after a successful reset", async () => {
    vi.mocked(resetPassword).mockResolvedValue({ status: "ok" });

    render(<ResetPasswordForm token="opaque-token" />);

    await userEvent.type(screen.getByLabelText(/^new password/i), "new-safe-passphrase");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "new-safe-passphrase");
    await userEvent.click(screen.getByRole("button", { name: /reset password/i }));

    expect(resetPassword).toHaveBeenCalledWith("opaque-token", "new-safe-passphrase");
    expect(replace).toHaveBeenCalledWith("/login?reset=success");
    expect(refresh).toHaveBeenCalled();
  });
});
