import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SiteHeader } from "@/components/layout/SiteHeader";

const copy = {
  common: {
    nav: {
      home: "Home",
      services: "Services",
      coverage: "Coverage",
      contact: "Contact",
      apply: "Apply",
      login: "Login",
    },
    language: {
      next: "ES",
      aria: "Switch to Spanish",
    },
  },
};

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

vi.mock("@/components/layout/LocaleProvider", () => ({
  useLocale: () => ({ copy, toggleLocale: vi.fn() }),
}));

describe("public navigation", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_BACKOFFICE_URL = "https://demo-backoffice.example/";
  });

  it("uses the configured Back Office URL and Login label in the header", () => {
    render(<SiteHeader />);

    expect(screen.getByRole("link", { name: "Login" })).toHaveAttribute(
      "href",
      "https://demo-backoffice.example",
    );
    expect(screen.queryByText("Back Office Login")).not.toBeInTheDocument();
  });

  it("reveals every destination through the mobile disclosure and points Login at the Back Office", () => {
    render(<SiteHeader />);

    const trigger = screen.getByRole("button", { name: /open navigation/i });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("navigation", { name: /mobile navigation/i })).not.toBeInTheDocument();

    fireEvent.click(trigger);

    const openedTrigger = screen.getByRole("button", { name: /close navigation/i });
    expect(openedTrigger).toHaveAttribute("aria-expanded", "true");

    const mobileNavigation = screen.getByRole("navigation", { name: /mobile navigation/i });
    expect(within(mobileNavigation).getByRole("link", { name: "Login" })).toHaveAttribute(
      "href",
      "https://demo-backoffice.example",
    );
    // The panel carries the apply destination the desktop header renders elsewhere.
    expect(within(mobileNavigation).getByRole("link", { name: "Apply" })).toHaveAttribute(
      "href",
      "/application",
    );

    fireEvent.click(openedTrigger);
    expect(screen.getByRole("button", { name: /open navigation/i })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("closes the mobile disclosure on Escape", () => {
    render(<SiteHeader />);

    fireEvent.click(screen.getByRole("button", { name: /open navigation/i }));
    expect(screen.getByRole("navigation", { name: /mobile navigation/i })).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("navigation", { name: /mobile navigation/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open navigation/i })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });
});
