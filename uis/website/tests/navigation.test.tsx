import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MobileNav } from "@/components/layout/MobileNav";
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

  it("keeps Login in the mobile navigation", () => {
    render(<MobileNav />);

    const mobileNavigation = screen.getByRole("navigation", {
      name: /mobile navigation/i,
    });
    expect(within(mobileNavigation).getByRole("link", { name: "Login" })).toHaveAttribute(
      "href",
      "https://demo-backoffice.example",
    );
  });
});
