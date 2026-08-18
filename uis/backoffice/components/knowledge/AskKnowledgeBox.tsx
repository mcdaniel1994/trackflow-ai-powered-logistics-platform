"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, ArrowUp, Clock3, Loader2, MessageSquarePlus, Sparkles, X } from "lucide-react";
import { agentError, createChatSession, getChatSession, listChatSessions } from "@/lib/agents/api";
import type { AgentRoute, ChatMessage, ChatSession } from "@/lib/agents/types";
import { ChatSocketClient } from "@/lib/realtime/chat";
import type { ChatConnectionState, ChatSocketEvent } from "@/lib/realtime/chat";

const SUGGESTIONS = [
  "What's the standard return window?",
  "Which carrier best covers rural Aragón?",
  "Can we promise our delivery SLA on Black Friday?",
  "What is the status of ticket 1?",
];

const ROUTES: { value: AgentRoute; label: string; description: string }[] = [
  { value: "auto", label: "Auto", description: "Let the CX agent choose the best source" },
  { value: "knowledge", label: "Knowledge base", description: "Use policies, SLAs, and procedures" },
  { value: "ticket", label: "Ticket lookup", description: "Use a specific ticket or order number" },
];

type Status = "idle" | "connecting" | "streaming" | "error";
type DisplayMessage = Pick<ChatMessage, "role" | "content" | "interrupted"> & {
  message_id: string;
  route_taken?: string;
};

function sessionLabel(session: ChatSession) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(session.updated_at));
}

function routeLabel(route: string) {
  if (route.startsWith("rag")) return "Knowledge base";
  if (route === "ticket") return "Ticket lookup";
  if (route === "both") return "Knowledge + ticket";
  return route;
}

export function AskKnowledgeBox() {
  const [question, setQuestion] = useState("");
  const [panelQuestion, setPanelQuestion] = useState("");
  const [route, setRoute] = useState<AgentRoute>("auto");
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [panelOpen, setPanelOpen] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSession, setActiveSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [connectionState, setConnectionState] = useState<ChatConnectionState>("disconnected");
  const launcherInputRef = useRef<HTMLTextAreaElement>(null);
  const panelInputRef = useRef<HTMLTextAreaElement>(null);
  const socketRef = useRef<ChatSocketClient | null>(null);
  const tokenSequencesRef = useRef<Record<string, number>>({});

  const refreshSessions = useCallback(async () => {
    try {
      setSessions(await listChatSessions());
    } catch {
      // The feature is off by default. A send attempt surfaces an actionable error in the panel.
    }
  }, []);

  const handleSocketEvent = useCallback((frame: ChatSocketEvent) => {
    const { event, data } = frame;
    if (event === "session_snapshot") {
      const snapshotMessages = Array.isArray(data.messages) ? data.messages as ChatMessage[] : [];
      const active = data.active_generation && typeof data.active_generation === "object"
        ? data.active_generation as Record<string, unknown>
        : null;
      const generationId = typeof active?.generation_id === "string" ? active.generation_id : null;
      const partial = typeof active?.content === "string" ? active.content : "";
      const sequence = typeof active?.sequence === "number" ? active.sequence : 0;
      tokenSequencesRef.current = generationId ? { [generationId]: sequence } : {};
      setMessages(generationId && partial
        ? [...snapshotMessages, {
            message_id: `stream-${generationId}`,
            role: "assistant",
            content: partial,
            interrupted: false,
          }]
        : snapshotMessages);
      setStatus(generationId ? "streaming" : "idle");
      setErrorMessage("");
      return;
    }
    if (event === "user_message" && data.message && typeof data.message === "object") {
      const message = data.message as unknown as ChatMessage;
      setMessages((current) => {
        if (current.some((row) => row.message_id === message.message_id)) return current;
        const pending = current.findIndex(
          (row) => row.role === "user" && row.message_id.startsWith("pending-user-") && row.content === message.content,
        );
        if (pending < 0) return [...current, message];
        return current.map((row, index) => index === pending ? message : row);
      });
      return;
    }
    const generationId = typeof data.generation_id === "string" ? data.generation_id : "unknown";
    const draftId = `stream-${generationId}`;
    if (event === "token_chunk" && typeof data.token === "string") {
      const sequence = typeof data.sequence === "number" ? data.sequence : 0;
      if (sequence && sequence <= (tokenSequencesRef.current[generationId] ?? 0)) return;
      if (sequence) tokenSequencesRef.current[generationId] = sequence;
      setStatus("streaming");
      setMessages((current) => {
        const existing = current.find((row) => row.message_id === draftId);
        if (!existing) {
          return [...current, { message_id: draftId, role: "assistant", content: data.token as string, interrupted: false }];
        }
        return current.map((row) => row.message_id === draftId ? { ...row, content: row.content + data.token } : row);
      });
      return;
    }
    if (event === "generation_completed") {
      delete tokenSequencesRef.current[generationId];
      const messageId = typeof data.message_id === "string" ? data.message_id : draftId;
      const routeTaken = typeof data.route_taken === "string" ? data.route_taken : undefined;
      setMessages((current) => current.map((row) => row.message_id === draftId
        ? { ...row, message_id: messageId, route_taken: routeTaken }
        : row));
      setStatus("idle");
      void refreshSessions();
      return;
    }
    if (event === "generation_interrupted") {
      delete tokenSequencesRef.current[generationId];
      const messageId = typeof data.message_id === "string" ? data.message_id : draftId;
      setMessages((current) => current.map((row) => row.message_id === draftId
        ? { ...row, message_id: messageId, interrupted: true }
        : row));
      setStatus("idle");
      void refreshSessions();
      return;
    }
    if (event === "generation_failed") {
      setErrorMessage(typeof data.detail === "string" ? data.detail : "The assistant is temporarily unavailable.");
      setStatus("error");
    }
  }, [refreshSessions]);

  const connectSession = useCallback((sessionId: string) => {
    socketRef.current?.close();
    const socket = new ChatSocketClient({
      sessionId,
      onEvent: handleSocketEvent,
      onStateChange: setConnectionState,
    });
    socketRef.current = socket;
    socket.connect();
    return socket;
  }, [handleSocketEvent]);

  useEffect(() => {
    let mounted = true;
    void listChatSessions()
      .then((rows) => {
        if (mounted) setSessions(rows);
      })
      .catch(() => {
        // The feature is intentionally off by default.
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => () => socketRef.current?.close(), []);

  useEffect(() => {
    if (!panelOpen) return;
    panelInputRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPanelOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [panelOpen]);

  function closePanel() {
    setPanelOpen(false);
    window.setTimeout(() => launcherInputRef.current?.focus(), 0);
  }

  async function submit(raw: string) {
    const trimmed = raw.trim();
    if (!trimmed || status === "connecting") return;

    setPanelOpen(true);
    setQuestion("");
    setPanelQuestion("");
    setStatus((current) => current === "streaming" ? current : "connecting");
    setErrorMessage("");
    setMessages((current) => [
      ...current,
      { message_id: `pending-user-${Date.now()}`, role: "user", content: trimmed, interrupted: false },
    ]);

    let session = activeSession;
    try {
      if (!session) {
        session = await createChatSession();
        setActiveSession(session);
        setSessions((current) => [session as ChatSession, ...current]);
      }
      const socket = socketRef.current ?? connectSession(session.session_id);
      if (status === "streaming") {
        socket.interrupt(trimmed, route);
      } else {
        socket.sendUserMessage(trimmed, route);
      }
      setStatus("streaming");
    } catch (error) {
      setErrorMessage(agentError(error).message);
      setStatus("error");
    }
  }

  async function openSession(sessionId: string) {
    if (!sessionId) return;
    setPanelOpen(true);
    setStatus("connecting");
    setErrorMessage("");
    try {
      const detail = await getChatSession(sessionId);
      setActiveSession(detail);
      setMessages(detail.messages);
      connectSession(detail.session_id);
      setStatus("idle");
    } catch (error) {
      setErrorMessage(agentError(error).message);
      setStatus("error");
    }
  }

  function startNewChat() {
    socketRef.current?.close();
    socketRef.current = null;
    setActiveSession(null);
    setMessages([]);
    setErrorMessage("");
    setStatus("idle");
    setConnectionState("disconnected");
    setPanelOpen(true);
  }

  const selectedRoute = ROUTES.find((option) => option.value === route) ?? ROUTES[0];

  return (
    <>
      <section
        aria-label="Ask the knowledge base"
        className="rounded-2xl border border-mist bg-white p-5 shadow-soft dark:border-ink-600 dark:bg-ink-800 sm:p-6"
      >
        <div className="mb-3 flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-navy text-white dark:bg-sky">
            <Sparkles className="h-5 w-5" aria-hidden="true" />
          </span>
          <div>
            <h2 className="text-base font-black text-navy-deep dark:text-neutral-100">Ask your CX agent</h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-300">
              Grounded in TrackFlow policy documents and live ticket status — never invented.
            </p>
          </div>
        </div>

        <form onSubmit={(event) => { event.preventDefault(); void submit(question); }}>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <label htmlFor="knowledge-agent-route" className="text-xs font-bold text-neutral-500 dark:text-neutral-300">Agent route</label>
            <select
              id="knowledge-agent-route"
              value={route}
              onChange={(event) => setRoute(event.target.value as AgentRoute)}
              className="rounded-lg border border-mist bg-white px-2.5 py-1.5 text-xs font-bold text-navy outline-none focus:border-sky dark:border-ink-600 dark:bg-ink-700 dark:text-neutral-100"
            >
              {ROUTES.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
            <span className="text-xs text-neutral-400">{selectedRoute.description}</span>
          </div>
          <div className="flex items-end gap-2 rounded-xl border border-mist bg-neutral-50 p-2 focus-within:border-sky dark:border-ink-600 dark:bg-ink-700">
            <label htmlFor="knowledge-question" className="sr-only">Type what you&rsquo;re looking for or ask a question</label>
            <textarea
              ref={launcherInputRef}
              id="knowledge-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void submit(question);
                }
              }}
              rows={2}
              placeholder="Type what you're looking for or ask a question"
              className="min-h-[2.75rem] w-full resize-none bg-transparent px-2 py-1.5 text-sm text-navy-deep outline-none placeholder:text-neutral-400 dark:text-neutral-100 dark:placeholder:text-neutral-500"
            />
            <button
              type="submit"
              disabled={status === "connecting" || !question.trim()}
              aria-label="Ask"
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-navy text-white transition hover:bg-navy-deep disabled:cursor-not-allowed disabled:opacity-40 dark:bg-sky dark:hover:bg-teal"
            >
              {status === "connecting" ? <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" /> : <ArrowUp className="h-5 w-5" aria-hidden="true" />}
            </button>
          </div>
        </form>

        <div className="mt-3 flex flex-wrap gap-2">
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => void submit(suggestion)}
              className="rounded-full border border-mist bg-white px-3 py-1.5 text-xs font-bold text-navy transition hover:border-sky hover:bg-ivory dark:border-ink-600 dark:bg-ink-700 dark:text-neutral-200 dark:hover:border-sky"
            >
              {suggestion}
            </button>
          ))}
        </div>

        {sessions.length ? (
          <button type="button" onClick={() => void openSession(sessions[0].session_id)} className="mt-4 inline-flex items-center gap-2 text-xs font-bold text-navy hover:text-sky dark:text-neutral-200">
            <Clock3 className="h-4 w-4" aria-hidden="true" /> Resume recent conversation
          </button>
        ) : null}
      </section>

      {panelOpen ? (
        <div className="fixed inset-0 z-50">
          <button type="button" aria-label="Close chat" onClick={closePanel} className="absolute inset-0 bg-navy-deep/35 backdrop-blur-[1px]" />
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="chat-panel-title"
            className="absolute inset-0 flex bg-white shadow-2xl dark:bg-ink-900 sm:inset-y-0 sm:left-auto sm:right-0 sm:w-[min(48rem,calc(100vw-2rem))] sm:border-l sm:border-mist dark:sm:border-ink-600"
          >
            <aside className="hidden w-56 shrink-0 border-r border-mist bg-neutral-50 p-4 dark:border-ink-600 dark:bg-ink-800 md:block">
              <button type="button" onClick={startNewChat} className="mb-5 flex w-full items-center justify-center gap-2 rounded-lg bg-navy px-3 py-2.5 text-sm font-black text-white hover:bg-navy-deep dark:bg-sky">
                <MessageSquarePlus className="h-4 w-4" aria-hidden="true" /> New chat
              </button>
              <h3 className="mb-2 text-xs font-black uppercase tracking-wide text-neutral-400">History</h3>
              <div className="space-y-1">
                {sessions.length ? sessions.map((session) => (
                  <button
                    key={session.session_id}
                    type="button"
                    onClick={() => void openSession(session.session_id)}
                    aria-current={activeSession?.session_id === session.session_id ? "true" : undefined}
                    className="w-full rounded-lg px-3 py-2 text-left text-xs font-bold text-neutral-600 hover:bg-white aria-[current=true]:bg-white aria-[current=true]:text-navy dark:text-neutral-300 dark:hover:bg-ink-700 dark:aria-[current=true]:bg-ink-700 dark:aria-[current=true]:text-white"
                  >
                    {sessionLabel(session)}
                  </button>
                )) : <p className="text-xs text-neutral-400">No previous conversations.</p>}
              </div>
            </aside>

            <div className="flex min-w-0 flex-1 flex-col">
              <header className="flex items-center justify-between border-b border-mist px-4 py-3 dark:border-ink-600 sm:px-5">
                <div>
                  <h2 id="chat-panel-title" className="font-black text-navy-deep dark:text-neutral-100">First-line CX agent</h2>
                  <p className="text-xs text-neutral-400">
                    {selectedRoute.label} route · {connectionState === "reconnecting" ? "reconnecting…" : connectionState}
                  </p>
                </div>
                <button type="button" onClick={closePanel} aria-label="Close chat" className="flex h-10 w-10 items-center justify-center rounded-lg border border-mist text-navy hover:bg-ivory dark:border-ink-600 dark:text-neutral-100 dark:hover:bg-ink-700">
                  <X className="h-5 w-5" aria-hidden="true" />
                </button>
              </header>

              <div className="border-b border-mist px-4 py-2 dark:border-ink-600 md:hidden">
                <div className="flex items-center gap-2">
                  <button type="button" onClick={startNewChat} className="rounded-lg bg-navy px-3 py-2 text-xs font-bold text-white dark:bg-sky">New chat</button>
                  <label htmlFor="mobile-chat-history" className="sr-only">Conversation history</label>
                  <select id="mobile-chat-history" value={activeSession?.session_id ?? ""} onChange={(event) => void openSession(event.target.value)} className="min-w-0 flex-1 rounded-lg border border-mist bg-white px-2 py-2 text-xs text-navy dark:border-ink-600 dark:bg-ink-800 dark:text-neutral-100">
                    <option value="">Conversation history</option>
                    {sessions.map((session) => <option key={session.session_id} value={session.session_id}>{sessionLabel(session)}</option>)}
                  </select>
                </div>
              </div>

              <div aria-live="polite" className="flex-1 space-y-4 overflow-y-auto px-4 py-5 sm:px-6">
                {!messages.length && status !== "connecting" && status !== "streaming" ? (
                  <div className="mx-auto mt-12 max-w-sm text-center">
                    <Sparkles className="mx-auto mb-3 h-8 w-8 text-sky" aria-hidden="true" />
                    <p className="font-black text-navy-deep dark:text-neutral-100">How can I help?</p>
                    <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-300">Ask about returns, delivery policy, carriers, or a specific ticket.</p>
                  </div>
                ) : null}
                {messages.map((message) => (
                  <div key={message.message_id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${message.role === "user" ? "bg-navy text-white dark:bg-sky" : "border border-mist bg-neutral-50 text-navy-deep dark:border-ink-600 dark:bg-ink-800 dark:text-neutral-100"}`}>
                      <p className="whitespace-pre-wrap">{message.content}</p>
                      {message.route_taken ? <p className="mt-2 text-[0.68rem] font-bold uppercase tracking-wide text-neutral-400">Via {routeLabel(message.route_taken)}</p> : null}
                      {message.interrupted ? <p className="mt-2 text-xs italic text-coral">Response interrupted</p> : null}
                    </div>
                  </div>
                ))}
                {status === "connecting" ? <div className="flex items-center gap-2 text-sm text-neutral-400"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Connecting&hellip;</div> : null}
                {status === "streaming" ? <div className="flex items-center justify-between gap-3 text-sm text-neutral-400"><span className="flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Agent is responding&hellip;</span><button type="button" onClick={() => socketRef.current?.interrupt(null, route)} className="rounded-lg border border-coral/50 px-3 py-1.5 text-xs font-bold text-coral hover:bg-coral/10">Stop response</button></div> : null}
                {status === "error" ? <div role="alert" className="flex items-start gap-2 rounded-xl border border-coral/40 bg-coral/10 px-4 py-3 text-sm text-coral"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /><span>{errorMessage}</span></div> : null}
              </div>

              <form onSubmit={(event) => { event.preventDefault(); void submit(panelQuestion); }} className="border-t border-mist p-3 dark:border-ink-600 sm:p-4">
                <div className="mb-2 flex items-center gap-2">
                  <label htmlFor="panel-agent-route" className="text-xs font-bold text-neutral-500 dark:text-neutral-300">Agent route</label>
                  <select id="panel-agent-route" value={route} onChange={(event) => setRoute(event.target.value as AgentRoute)} className="rounded-lg border border-mist bg-white px-2 py-1.5 text-xs font-bold text-navy dark:border-ink-600 dark:bg-ink-800 dark:text-neutral-100">
                    {ROUTES.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                </div>
                <div className="flex items-end gap-2 rounded-xl border border-mist bg-neutral-50 p-2 focus-within:border-sky dark:border-ink-600 dark:bg-ink-800">
                  <label htmlFor="chat-panel-question" className="sr-only">Send a message</label>
                  <textarea ref={panelInputRef} id="chat-panel-question" value={panelQuestion} onChange={(event) => setPanelQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void submit(panelQuestion); } }} rows={2} placeholder="Send a message" className="min-h-[2.75rem] w-full resize-none bg-transparent px-2 py-1.5 text-sm text-navy-deep outline-none dark:text-neutral-100" />
                  <button type="submit" disabled={status === "connecting" || !panelQuestion.trim()} aria-label={status === "streaming" ? "Interrupt and redirect" : "Send message"} className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-navy text-white disabled:opacity-40 dark:bg-sky">
                    {status === "connecting" ? <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" /> : <ArrowUp className="h-5 w-5" aria-hidden="true" />}
                  </button>
                </div>
              </form>
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}
