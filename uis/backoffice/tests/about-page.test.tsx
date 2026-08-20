import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AboutPage from "@/app/(protected)/about/page";
import { DISCLAIMERS, NOTABLE_LICENSES, TECH_STACK } from "@/content/about";

describe("About & disclaimers page", () => {
  it("leads with the portfolio disclaimer", () => {
    render(<AboutPage />);

    // The reader must learn this is not a real service before anything else on
    // the page invites them to take it literally.
    const headings = screen.getAllByRole("heading", { level: 2 });
    expect(headings[0]).toHaveTextContent("Important disclaimers");
    // Stated in both the lede and the disclaimer list, deliberately.
    expect(screen.getAllByText(/is a portfolio project/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/All data in this application is synthetic/i)).toBeInTheDocument();
  });

  it("renders every disclaimer", () => {
    render(<AboutPage />);
    for (const item of DISCLAIMERS) {
      expect(screen.getByText(item)).toBeInTheDocument();
    }
  });

  it("states that cost estimates are not binding quotations", () => {
    render(<AboutPage />);
    expect(screen.getByText(/not binding quotations/i)).toBeInTheDocument();
  });

  it("lists each technology layer", () => {
    render(<AboutPage />);
    for (const group of TECH_STACK) {
      expect(screen.getByText(group.layer)).toBeInTheDocument();
    }
  });

  it("renders the license table with a row per project", () => {
    render(<AboutPage />);
    const table = screen.getByRole("table");

    for (const row of NOTABLE_LICENSES) {
      expect(within(table).getByText(row.name)).toBeInTheDocument();
    }
    expect(within(table).getByRole("columnheader", { name: "License" })).toBeInTheDocument();
  });

  it("does not claim the license list is exhaustive", () => {
    render(<AboutPage />);
    // THIRD_PARTY_LICENSES.md deliberately does not enumerate ~650 permissive
    // packages, so the page must not imply this summary is complete.
    expect(screen.getByText(/rather than a complete inventory/i)).toBeInTheDocument();
    expect(screen.getByText(/THIRD_PARTY_LICENSES\.md/)).toBeInTheDocument();
  });

  it("uses exactly one level-one heading", () => {
    render(<AboutPage />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });
});
