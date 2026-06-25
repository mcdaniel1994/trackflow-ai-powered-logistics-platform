import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import GlobalError from "@/app/global-error";
import NotFound from "@/app/not-found";
import ProtectedError from "@/app/(protected)/error";

describe("Back Office error surfaces", () => {
  it("renders the global error boundary without exposing the thrown message", async () => {
    const reset = vi.fn();
    render(<GlobalError error={new Error("reset-link-secret should stay hidden")} reset={reset} />);

    expect(screen.getByRole("heading", { name: /something went wrong/i })).toBeInTheDocument();
    expect(screen.queryByText(/reset-link-secret/i)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(reset).toHaveBeenCalledTimes(1);
  });

  it("renders the protected error boundary without exposing the thrown message", async () => {
    const reset = vi.fn();
    render(<ProtectedError error={new Error("access-token should stay hidden")} reset={reset} />);

    expect(screen.getByRole("heading", { name: /this view could not load/i })).toBeInTheDocument();
    expect(screen.queryByText(/access-token/i)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(reset).toHaveBeenCalledTimes(1);
  });

  it("renders a generic not-found page", () => {
    render(<NotFound />);

    expect(screen.getByRole("heading", { name: /page not found/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to dashboard/i })).toHaveAttribute("href", "/");
  });
});
