import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const knowledgeMocks = vi.hoisted(() => ({
  askKnowledge: vi.fn(),
}));

vi.mock("@/lib/knowledge/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/knowledge/api")>("@/lib/knowledge/api");
  return { ...actual, askKnowledge: knowledgeMocks.askKnowledge };
});

import { AskKnowledgeBox } from "@/components/knowledge/AskKnowledgeBox";

describe("Ask knowledge base", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("submits a question and renders the generated answer", async () => {
    knowledgeMocks.askKnowledge.mockResolvedValue({ answer: "Our standard return window is 30 days." });
    render(<AskKnowledgeBox />);

    await userEvent.type(screen.getByLabelText(/ask a question/i), "return window?");
    await userEvent.click(screen.getByRole("button", { name: /^ask$/i }));

    expect(await screen.findByText("Our standard return window is 30 days.")).toBeInTheDocument();
    expect(knowledgeMocks.askKnowledge).toHaveBeenCalledWith("return window?");
  });

  it("shows an error message when the request fails", async () => {
    knowledgeMocks.askKnowledge.mockRejectedValue({ message: "The knowledge base is not available right now.", status: 503 });
    render(<AskKnowledgeBox />);

    await userEvent.type(screen.getByLabelText(/ask a question/i), "anything");
    await userEvent.click(screen.getByRole("button", { name: /^ask$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/not available right now/i);
  });

  it("asks a suggested question in one click", async () => {
    knowledgeMocks.askKnowledge.mockResolvedValue({ answer: "SEUR covers rural Aragón best." });
    render(<AskKnowledgeBox />);

    await userEvent.click(screen.getByRole("button", { name: /rural Aragón/i }));

    await waitFor(() =>
      expect(knowledgeMocks.askKnowledge).toHaveBeenCalledWith("Which carrier best covers rural Aragón?"),
    );
    expect(await screen.findByText("SEUR covers rural Aragón best.")).toBeInTheDocument();
  });

  it("does not submit a blank question", async () => {
    render(<AskKnowledgeBox />);
    const askButton = screen.getByRole("button", { name: /^ask$/i });
    expect(askButton).toBeDisabled();
    await userEvent.click(askButton);
    expect(knowledgeMocks.askKnowledge).not.toHaveBeenCalled();
  });
});
