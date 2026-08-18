import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const agentMocks = vi.hoisted(() => ({
  createChatSession: vi.fn(),
  getChatSession: vi.fn(),
  listChatSessions: vi.fn(),
}));

const socketMocks = vi.hoisted(() => {
  const instances: Array<{
    options: {
      sessionId: string;
      onEvent: (frame: { event: string; data: Record<string, unknown> }) => void;
      onStateChange: (state: string) => void;
    };
    connect: ReturnType<typeof vi.fn>;
    sendUserMessage: ReturnType<typeof vi.fn>;
    interrupt: ReturnType<typeof vi.fn>;
    close: ReturnType<typeof vi.fn>;
  }> = [];
  const ChatSocketClient = vi.fn(function ChatSocketClient(options: {
    sessionId: string;
    onEvent: (frame: { event: string; data: Record<string, unknown> }) => void;
    onStateChange: (state: string) => void;
  }) {
    const instance = {
      options,
      connect: vi.fn(() => options.onStateChange("connected")),
      sendUserMessage: vi.fn(),
      interrupt: vi.fn(),
      close: vi.fn(),
    };
    instances.push(instance);
    return instance;
  });
  return { ChatSocketClient, instances };
});

vi.mock("@/lib/agents/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/agents/api")>("@/lib/agents/api");
  return { ...actual, ...agentMocks };
});

vi.mock("@/lib/realtime/chat", () => ({ ChatSocketClient: socketMocks.ChatSocketClient }));

import { AskKnowledgeBox } from "@/components/knowledge/AskKnowledgeBox";

const session = {
  session_id: "11111111-1111-4111-8111-111111111111",
  agent_id: "first_line_cx" as const,
  user_id: "owner",
  client_id: "owner",
  status: "active" as const,
  created_at: "2026-08-18T12:00:00Z",
  updated_at: "2026-08-18T12:00:00Z",
};

function emit(event: string, data: Record<string, unknown>) {
  const socket = socketMocks.instances.at(-1);
  if (!socket) throw new Error("socket was not created");
  act(() => socket.options.onEvent({ event, data }));
}

describe("Ask knowledge base", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    socketMocks.instances.length = 0;
    agentMocks.listChatSessions.mockResolvedValue([]);
    agentMocks.createChatSession.mockResolvedValue(session);
    agentMocks.getChatSession.mockResolvedValue({ ...session, messages: [] });
  });

  it("opens immediately, clears input, and renders progressive server tokens", async () => {
    render(<AskKnowledgeBox />);

    const input = screen.getByLabelText(/ask a question/i);
    await userEvent.type(input, "return window?");
    await userEvent.click(screen.getByRole("button", { name: /^ask$/i }));

    expect(screen.getByRole("dialog", { name: /first-line cx agent/i })).toBeInTheDocument();
    expect(input).toHaveValue("");
    await waitFor(() => expect(socketMocks.instances).toHaveLength(1));
    const socket = socketMocks.instances[0];
    expect(socket.options.sessionId).toBe(session.session_id);
    expect(socket.connect).toHaveBeenCalledOnce();
    expect(socket.sendUserMessage).toHaveBeenCalledWith("return window?", "auto");

    emit("session_snapshot", {
      messages: [],
      active_generation: { generation_id: "g1", content: "Our standard ", sequence: 1 },
    });
    expect(screen.getByText("Our standard")).toBeInTheDocument();
    emit("token_chunk", { generation_id: "g1", token: "Our standard ", sequence: 1 });
    emit("token_chunk", { generation_id: "g1", token: "return window is 30 days.", sequence: 2 });
    expect(screen.getByText("Our standard return window is 30 days.")).toBeInTheDocument();
    emit("generation_completed", { generation_id: "g1", message_id: "answer-1", route_taken: "rag" });
    expect(screen.getByText(/via knowledge base/i)).toBeInTheDocument();
  });

  it("surfaces a safe server failure in the open chat panel", async () => {
    render(<AskKnowledgeBox />);
    await userEvent.type(screen.getByLabelText(/ask a question/i), "anything");
    await userEvent.click(screen.getByRole("button", { name: /^ask$/i }));
    await waitFor(() => expect(socketMocks.instances).toHaveLength(1));

    emit("generation_failed", { detail: "The assistant is not available right now." });
    expect(await screen.findByRole("alert")).toHaveTextContent(/not available right now/i);
  });

  it("sends a suggested question in one click", async () => {
    render(<AskKnowledgeBox />);
    await userEvent.click(screen.getByRole("button", { name: /rural Aragón/i }));

    await waitFor(() => expect(socketMocks.instances[0]?.sendUserMessage).toHaveBeenCalledWith(
      "Which carrier best covers rural Aragón?",
      "auto",
    ));
  });

  it("pins the selected route and does not submit a blank question", async () => {
    render(<AskKnowledgeBox />);
    const askButton = screen.getByRole("button", { name: /^ask$/i });
    expect(askButton).toBeDisabled();

    await userEvent.selectOptions(screen.getByLabelText("Agent route"), "knowledge");
    await userEvent.type(screen.getByLabelText(/ask a question/i), "returns policy");
    await userEvent.click(askButton);

    await waitFor(() => expect(socketMocks.instances[0]?.sendUserMessage).toHaveBeenCalledWith(
      "returns policy",
      "knowledge",
    ));
  });

  it("interrupts an active generation and redirects it with the new input", async () => {
    render(<AskKnowledgeBox />);
    await userEvent.type(screen.getByLabelText(/ask a question/i), "track parcel");
    await userEvent.click(screen.getByRole("button", { name: /^ask$/i }));
    await waitFor(() => expect(socketMocks.instances).toHaveLength(1));
    emit("token_chunk", { generation_id: "g1", token: "Tracking", sequence: 1 });

    await userEvent.type(screen.getByLabelText("Send a message"), "start a return");
    await userEvent.click(screen.getByRole("button", { name: /interrupt and redirect/i }));
    expect(socketMocks.instances[0].interrupt).toHaveBeenCalledWith("start a return", "auto");

    await userEvent.click(screen.getByRole("button", { name: /stop response/i }));
    expect(socketMocks.instances[0].interrupt).toHaveBeenLastCalledWith(null, "auto");
  });

  it("restores an owner session, accepts its authoritative snapshot, and closes with Escape", async () => {
    agentMocks.listChatSessions.mockResolvedValue([session]);
    agentMocks.getChatSession.mockResolvedValue({
      ...session,
      messages: [{
        message_id: "message-1",
        session_id: session.session_id,
        role: "assistant" as const,
        content: "Cached answer",
        sequence: 1,
        interrupted: false,
        created_at: session.created_at,
      }],
    });
    render(<AskKnowledgeBox />);

    expect(await screen.findByRole("button", { name: /resume recent conversation/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /resume recent conversation/i }));
    expect(await screen.findByText("Cached answer")).toBeInTheDocument();
    emit("session_snapshot", {
      session_id: session.session_id,
      status: "active",
      messages: [{
        message_id: "message-2",
        session_id: session.session_id,
        role: "assistant",
        content: "Authoritative answer",
        sequence: 1,
        interrupted: false,
        created_at: session.created_at,
      }],
    });
    expect(screen.getByText("Authoritative answer")).toBeInTheDocument();
    expect(screen.queryByText("Cached answer")).not.toBeInTheDocument();

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
