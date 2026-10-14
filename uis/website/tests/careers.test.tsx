import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CareersPage } from "@/components/careers/CareersPage";
import { LocaleProvider } from "@/components/layout/LocaleProvider";
import { SiteFooter } from "@/components/layout/SiteFooter";

const show = () =>
  render(
    <LocaleProvider>
      <CareersPage />
    </LocaleProvider>,
  );
describe("careers demonstration", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });
  it("links Careers in the footer and preselects an illustrative role", () => {
    render(
      <LocaleProvider>
        <SiteFooter />
        <CareersPage />
      </LocaleProvider>,
    );
    expect(screen.getByRole("link", { name: "Careers" })).toHaveAttribute(
      "href",
      "/careers",
    );
    fireEvent.click(
      within(
        screen
          .getByRole("heading", { name: "Warehouse Associate — Los Angeles" })
          .closest("article")!,
      ).getByRole("button"),
    );
    expect(screen.getByRole("combobox", { name: "Role" })).toHaveValue(
      "warehouse_associate",
    );
    expect(screen.getByText(/not active vacancies/)).toBeInTheDocument();
  });
  it("rejects real email addresses before sending", () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    show();
    fireEvent.click(screen.getByText("Fill sample application"));
    fireEvent.change(screen.getByLabelText(/Demo email/), {
      target: { value: "actual@company.com" },
    });
    fireEvent.click(screen.getByText("Submit demo application"));
    expect(screen.getByText(/Use an email ending in/)).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });
  it("shows confirmed creation and an authenticated candidate link", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ candidate_id: "candidate-42" }), {
          status: 201,
        }),
      );
    vi.stubGlobal("fetch", fetch);
    show();
    fireEvent.click(screen.getByText("Fill sample application"));
    fireEvent.click(screen.getByText("Submit demo application"));
    fireEvent.click(screen.getByText("Submitting…"));
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(
      await screen.findByText("Demo application received"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "View in Back Office" }),
    ).toHaveAttribute(
      "href",
      "https://backoffice.forgehub.cloud/talent/candidate-42",
    );
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toMatchObject({
      role: "general",
      experience_years: 3,
      demo_acknowledged: true,
    });
  });
  it("keeps ambiguous failures visible and prevents another write", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ code: "uncertain" }), { status: 504 }),
        ),
    );
    show();
    fireEvent.click(screen.getByText("Fill sample application"));
    fireEvent.click(screen.getByText("Submit demo application"));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        /Check the Talent Tracker before submitting again/,
      ),
    );
    expect(screen.getByText("Submit demo application")).toBeDisabled();
  });
});
