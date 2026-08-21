import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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
import { ChatPanel } from "@/components/knowledge/ChatPanel";
import { ChatPanelProvider } from "@/lib/chat/panel-context";

// The hero box and the chat panel are separate components sharing the ChatPanelProvider; render both.
function renderAsk() {
  return render(
    <ChatPanelProvider>
      <AskKnowledgeBox />
      <ChatPanel />
    </ChatPanelProvider>,
  );
}

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

function stubVisualViewport(initial: { width: number; height: number; offsetTop: number; offsetLeft: number }) {
  const viewport = Object.assign(new EventTarget(), {
    ...initial,
    pageTop: initial.offsetTop,
    pageLeft: initial.offsetLeft,
    scale: 1,
    onresize: null,
    onscroll: null,
    onscrollend: null,
  });
  vi.stubGlobal("visualViewport", viewport);
  return viewport;
}

describe("Ask knowledge base", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    socketMocks.instances.length = 0;
    agentMocks.listChatSessions.mockResolvedValue([]);
    agentMocks.createChatSession.mockResolvedValue(session);
    agentMocks.getChatSession.mockResolvedValue({ ...session, messages: [] });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("opens immediately, clears input, and renders progressive server tokens", async () => {
    renderAsk();

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

  it("replaces streamed tokens with the server's authoritative answer", async () => {
    // An output guardrail that fires mid-stream has already emitted the tokens
    // preceding it. Without replacement the blocked content stays on screen with the
    // refusal appended -- which is how a rate-disclosure guard ended up displaying
    // the rate it was blocking.
    renderAsk();
    await userEvent.type(screen.getByLabelText(/ask a question/i), "what does delivery cost?");
    await userEvent.click(screen.getByRole("button", { name: /^ask$/i }));
    await waitFor(() => expect(socketMocks.instances).toHaveLength(1));

    emit("token_chunk", { generation_id: "g9", token: "Standard costs 6.40", sequence: 1 });
    expect(screen.getByText("Standard costs 6.40")).toBeInTheDocument();

    emit("generation_completed", {
      generation_id: "g9",
      message_id: "answer-9",
      route_taken: "reject",
      answer: "I couldn't return that answer safely.",
    });

    expect(screen.getByText("I couldn't return that answer safely.")).toBeInTheDocument();
    expect(screen.queryByText(/6\.40/)).not.toBeInTheDocument();
  });

  it("keeps streamed content when the server sends no authoritative answer", async () => {
    renderAsk();
    await userEvent.type(screen.getByLabelText(/ask a question/i), "anything");
    await userEvent.click(screen.getByRole("button", { name: /^ask$/i }));
    await waitFor(() => expect(socketMocks.instances).toHaveLength(1));

    emit("token_chunk", { generation_id: "g8", token: "Streamed answer.", sequence: 1 });
    emit("generation_completed", { generation_id: "g8", message_id: "answer-8", route_taken: "rag" });

    expect(screen.getByText("Streamed answer.")).toBeInTheDocument();
  });

  it("keeps chat form controls at 16px so iOS Safari does not zoom the page", async () => {
    // Safari force-zooms the whole document when a focused control is under 16px.
    // That is what made the panel unusable on a phone: the layout was fine, but the
    // viewport was zoomed and panned, pushing the send button and message bubbles
    // off-screen. `text-base` is 16px; dropping back to text-sm/text-xs on mobile
    // silently reintroduces it.
    renderAsk();
    await userEvent.type(screen.getByLabelText(/ask a question/i), "anything");
    await userEvent.click(screen.getByRole("button", { name: /^ask$/i }));

    const panel = within(await screen.findByRole("dialog"));
    // Every focusable control inside the panel, not just the composer: focusing the
    // route or history select zooms the page just as readily.
    for (const control of [
      panel.getByLabelText(/send a message/i),
      panel.getByLabelText(/agent route/i),
      panel.getByLabelText(/conversation history/i),
    ]) {
      expect(control.className).toContain("text-base");
    }
  });

  it("pins the whole chat overlay to the visual viewport while the keyboard pans it", async () => {
    const viewport = stubVisualViewport({ width: 390, height: 520, offsetTop: 84, offsetLeft: 0 });
    renderAsk();
    await userEvent.type(screen.getByLabelText(/ask a question/i), "anything");
    await userEvent.click(screen.getByRole("button", { name: /^ask$/i }));

    const dialog = await screen.findByRole("dialog");
    const overlay = dialog.parentElement;
    expect(overlay).not.toBeNull();
    await waitFor(() => {
      expect(overlay).toHaveStyle({ top: "84px", left: "0px", width: "390px", height: "520px" });
    });

    Object.assign(viewport, { width: 844, height: 310, offsetTop: 46, offsetLeft: 12 });
    act(() => viewport.dispatchEvent(new Event("resize")));
    act(() => viewport.dispatchEvent(new Event("scroll")));

    await waitFor(() => {
      expect(overlay).toHaveStyle({ top: "46px", left: "12px", width: "844px", height: "310px" });
    });
  });

  it("keeps an in-flight question visible when a new session snapshot arrives empty", async () => {
    // A session created moments ago has nothing persisted yet, so its snapshot is
    // empty. Replacing state wholesale erased the question the sender was looking
    // at, flashed the empty state, then restored it when user_message landed.
    renderAsk();
    await userEvent.type(screen.getByLabelText(/ask a question/i), "what is the return window?");
    await userEvent.click(screen.getByRole("button", { name: /^ask$/i }));
    await waitFor(() => expect(socketMocks.instances).toHaveLength(1));

    const panel = within(await screen.findByRole("dialog"));
    expect(panel.getByText("what is the return window?")).toBeInTheDocument();

    emit("session_snapshot", { session_id: "s1", messages: [] });

    // Still on screen, and no empty state.
    expect(panel.getByText("what is the return window?")).toBeInTheDocument();
    expect(panel.queryByText(/how can i help\?/i)).not.toBeInTheDocument();
  });

  it("keeps responding after a snapshot acknowledges the question but has no generation yet", async () => {
    renderAsk();
    await userEvent.type(screen.getByLabelText(/ask a question/i), "what is the return window?");
    await userEvent.click(screen.getByRole("button", { name: /^ask$/i }));
    await waitFor(() => expect(socketMocks.instances).toHaveLength(1));

    const panel = within(await screen.findByRole("dialog"));
    expect(panel.getByText(/agent is responding/i)).toBeInTheDocument();

    emit("session_snapshot", {
      session_id: session.session_id,
      messages: [{
        message_id: "message-1",
        role: "user",
        content: "what is the return window?",
        interrupted: false,
      }],
      active_generation: null,
    });

    expect(panel.getByText("what is the return window?")).toBeInTheDocument();
    expect(panel.getByText(/agent is responding/i)).toBeInTheDocument();

    emit("user_message", {
      generation_id: "generation-1",
      message: {
        message_id: "message-1",
        role: "user",
        content: "what is the return window?",
        interrupted: false,
      },
    });
    expect(panel.getByText(/agent is responding/i)).toBeInTheDocument();

    emit("generation_completed", { generation_id: "generation-1", message_id: "answer-1" });
    expect(panel.queryByText(/agent is responding/i)).not.toBeInTheDocument();
  });

  it("adopts an authoritative snapshot for a session that already has history", async () => {
    renderAsk();
    await userEvent.type(screen.getByLabelText(/ask a question/i), "hello");
    await userEvent.click(screen.getByRole("button", { name: /^ask$/i }));
    await waitFor(() => expect(socketMocks.instances).toHaveLength(1));

    emit("session_snapshot", {
      session_id: "s1",
      messages: [
        { message_id: "m1", role: "user", content: "earlier question", interrupted: false },
        { message_id: "m2", role: "assistant", content: "earlier answer", interrupted: false },
      ],
    });

    const panel = within(await screen.findByRole("dialog"));
    expect(panel.getByText("earlier question")).toBeInTheDocument();
    expect(panel.getByText("earlier answer")).toBeInTheDocument();
    // The unacknowledged question is carried alongside the recovered history.
    expect(panel.getByText("hello")).toBeInTheDocument();
  });

  it("dismisses the on-screen keyboard after sending on a touch device", async () => {
    // On a phone the keyboard covers the transcript, so holding focus after send
    // hides the answer being streamed. Desktop keeps focus for a fast follow-up.
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: query.includes("coarse"),
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));

    renderAsk();
    await userEvent.type(screen.getByLabelText(/ask a question/i), "a question");
    await userEvent.click(screen.getByRole("button", { name: /^ask$/i }));
    await waitFor(() => expect(socketMocks.instances).toHaveLength(1));

    const composer = within(await screen.findByRole("dialog")).getByLabelText(/send a message/i);
    await waitFor(() => expect(document.activeElement).not.toBe(composer));

  });

  it("locks the page behind the panel and restores it on close", async () => {
    // The document kept scrolling under the dialog, and on iOS the browser scrolls
    // the page to reveal the focused composer when the keyboard opens, which slid
    // the overlay up and exposed the Back Office beneath it.
    window.scrollTo(0, 240);
    renderAsk();
    await userEvent.type(screen.getByLabelText(/ask a question/i), "anything");
    await userEvent.click(screen.getByRole("button", { name: /^ask$/i }));
    const dialog = await screen.findByRole("dialog");

    expect(document.body.style.position).toBe("fixed");
    expect(document.body.style.overflow).toBe("hidden");

    // The backdrop carries the same label, so scope to the header control.
    await userEvent.click(within(dialog).getByRole("button", { name: /close chat/i }));

    await waitFor(() => expect(document.body.style.position).not.toBe("fixed"));
    expect(document.body.style.overflow).not.toBe("hidden");
  });

  it("surfaces a safe server failure in the open chat panel", async () => {
    renderAsk();
    await userEvent.type(screen.getByLabelText(/ask a question/i), "anything");
    await userEvent.click(screen.getByRole("button", { name: /^ask$/i }));
    await waitFor(() => expect(socketMocks.instances).toHaveLength(1));

    emit("generation_failed", { detail: "The assistant is not available right now." });
    expect(await screen.findByRole("alert")).toHaveTextContent(/not available right now/i);
  });

  it("sends a suggested question in one click", async () => {
    renderAsk();
    await userEvent.click(screen.getByRole("button", { name: /rural Aragón/i }));

    await waitFor(() => expect(socketMocks.instances[0]?.sendUserMessage).toHaveBeenCalledWith(
      "Which carrier best covers rural Aragón?",
      "auto",
    ));
  });

  it("pins the selected route and does not submit a blank question", async () => {
    renderAsk();
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
    renderAsk();
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

  it("does not go idle when the interrupted generation ends before its redirected turn starts", async () => {
    renderAsk();
    await userEvent.type(screen.getByLabelText(/ask a question/i), "track parcel");
    await userEvent.click(screen.getByRole("button", { name: /^ask$/i }));
    await waitFor(() => expect(socketMocks.instances).toHaveLength(1));
    emit("user_message", {
      generation_id: "generation-1",
      message: { message_id: "question-1", role: "user", content: "track parcel", interrupted: false },
    });
    emit("token_chunk", { generation_id: "generation-1", token: "Tracking", sequence: 1 });

    const panel = within(await screen.findByRole("dialog"));
    await userEvent.type(panel.getByLabelText("Send a message"), "start a return");
    await userEvent.click(panel.getByRole("button", { name: /interrupt and redirect/i }));
    emit("generation_interrupted", { generation_id: "generation-1", message_id: "partial-1" });

    expect(panel.getByText(/agent is responding/i)).toBeInTheDocument();
    expect(panel.getByText("start a return")).toBeInTheDocument();

    emit("user_message", {
      generation_id: "generation-2",
      message: { message_id: "question-2", role: "user", content: "start a return", interrupted: false },
    });
    emit("generation_completed", { generation_id: "generation-2", message_id: "answer-2" });

    expect(panel.queryByText(/agent is responding/i)).not.toBeInTheDocument();
  });

  it("ignores a late terminal event from the generation that was redirected", async () => {
    renderAsk();
    await userEvent.type(screen.getByLabelText(/ask a question/i), "track parcel");
    await userEvent.click(screen.getByRole("button", { name: /^ask$/i }));
    await waitFor(() => expect(socketMocks.instances).toHaveLength(1));
    emit("user_message", {
      generation_id: "generation-1",
      message: { message_id: "question-1", role: "user", content: "track parcel", interrupted: false },
    });

    const panel = within(await screen.findByRole("dialog"));
    await userEvent.type(panel.getByLabelText("Send a message"), "start a return");
    await userEvent.click(panel.getByRole("button", { name: /interrupt and redirect/i }));
    emit("user_message", {
      generation_id: "generation-2",
      message: { message_id: "question-2", role: "user", content: "start a return", interrupted: false },
    });
    emit("generation_interrupted", { generation_id: "generation-1", message_id: "partial-1" });

    expect(panel.getByText(/agent is responding/i)).toBeInTheDocument();
    emit("generation_completed", { generation_id: "generation-2", message_id: "answer-2" });
    expect(panel.queryByText(/agent is responding/i)).not.toBeInTheDocument();
  });

  it("opens a recent conversation without creating a new chat session", async () => {
    agentMocks.listChatSessions.mockResolvedValue([session]);
    renderAsk();

    await userEvent.click(await screen.findByRole("button", { name: /resume recent conversation/i }));

    expect(await screen.findByRole("dialog", { name: /first-line cx agent/i })).toBeInTheDocument();
    // Opening issues no write: a session is created only when the first message is sent.
    expect(agentMocks.createChatSession).not.toHaveBeenCalled();
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
    renderAsk();

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
