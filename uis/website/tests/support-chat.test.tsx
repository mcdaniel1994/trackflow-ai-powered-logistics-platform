import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SupportChat } from "@/components/support/SupportChat";
import { LocaleProvider } from "@/components/layout/LocaleProvider";

beforeEach(() => {
  window.localStorage.clear();
});
afterEach(() => {
  vi.unstubAllGlobals();
});
function open() {
  render(
    <LocaleProvider>
      <SupportChat />
    </LocaleProvider>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Chat with TrackFlow" }));
}
it.each(["Hello", "Hi!", "Hola"])(
  "welcomes a greeting without a policy lookup: %s",
  (greeting) => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    open();
    fireEvent.change(screen.getByLabelText("Your question"), {
      target: { value: greeting },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Send$/ }));
    expect(screen.getByRole("log")).toHaveTextContent(
      "Hello! Welcome to TrackFlow.",
    );
    expect(screen.getByLabelText("Your question")).toHaveValue("");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  },
);
it("explains when policy answers have not been enabled instead of suggesting a retry", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ code: "not_enabled" }), { status: 503 }),
      ),
  );
  open();
  fireEvent.change(screen.getByLabelText("Policy country"), {
    target: { value: "US" },
  });
  fireEvent.change(screen.getByLabelText("Your question"), {
    target: { value: "Delivery policies?" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Policy answers have not been enabled in this demo yet.",
  );
  expect(screen.getByLabelText("Your question")).toHaveValue(
    "Delivery policies?",
  );
});
it("opens, focuses, dismisses with Escape and returns focus", () => {
  open();
  expect(
    screen.getByRole("dialog", { name: "TrackFlow Support" }),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Policy country")).toHaveFocus();
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Chat with TrackFlow" }),
  ).toHaveFocus();
});
it("requires policy country and uses only bounded completed exchanges as context", async () => {
  const fetch = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        answer: "Standard return window is 30 days.",
        outcome: "answered",
      }),
    ),
  );
  vi.stubGlobal("fetch", fetch);
  open();
  fireEvent.change(screen.getByLabelText("Your question"), {
    target: { value: "Returns?" },
  });
  fireEvent.click(screen.getByText("Send"));
  expect(fetch).not.toHaveBeenCalled();
  expect(screen.getByRole("alert")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Policy country"), {
    target: { value: "US" },
  });
  fireEvent.click(screen.getByText("Send"));
  expect(
    await screen.findByText("Standard return window is 30 days."),
  ).toBeInTheDocument();
  fetch.mockResolvedValue(
    new Response(
      JSON.stringify({ answer: "Ask your retailer.", outcome: "answered" }),
    ),
  );
  fireEvent.change(screen.getByLabelText("Your question"), {
    target: { value: "How do I request one?" },
  });
  fireEvent.click(screen.getByText("Send"));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toMatchObject({
    language: "en",
    policy_country: "US",
    recent_context: [
      { question: "Returns?", answer: "Standard return window is 30 days." },
    ],
  });
  expect(
    screen.getByRole("link", { name: "Contact TrackFlow" }),
  ).toHaveAttribute("href", "/#contact");
});
it("shows safe rate-limit feedback and retains the failed question for retry", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("", { status: 429 })),
  );
  open();
  fireEvent.change(screen.getByLabelText("Policy country"), {
    target: { value: "ES" },
  });
  fireEvent.change(screen.getByLabelText("Your question"), {
    target: { value: "Delivery?" },
  });
  fireEvent.click(screen.getByText("Send"));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    /try again in a minute/,
  );
  expect(screen.getByLabelText("Your question")).toHaveValue("Delivery?");
});

it("changes answer language independently of policy country", async () => {
  const fetch = vi
    .fn()
    .mockResolvedValue(
      new Response(
        JSON.stringify({ answer: "La política pública.", outcome: "answered" }),
      ),
    );
  vi.stubGlobal("fetch", fetch);
  open();
  fireEvent.change(screen.getByLabelText("Policy country"), {
    target: { value: "US" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Switch support chat to Spanish" }),
  );
  expect(
    screen.getByRole("dialog", { name: "Soporte de TrackFlow" }),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("País de la política")).toHaveValue("US");
  fireEvent.change(screen.getByLabelText("Tu pregunta"), { target: { value: "Hola" } });
  fireEvent.click(screen.getByRole("button", { name: /^Enviar$/ }));
  expect(screen.getByRole("log")).toHaveTextContent("¡Hola! Bienvenido a TrackFlow.");
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Tu pregunta"), {
    target: { value: "¿Qué servicios ofrecen?" },
  });
  fireEvent.click(screen.getByRole("button", { name: /^Enviar$/ }));
  await screen.findByText("La política pública.");
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toMatchObject({
    language: "es",
    policy_country: "US",
  });
  expect(window.localStorage.getItem("tf-lang")).toBe("es");
  expect(window.localStorage.length).toBe(1);
});
