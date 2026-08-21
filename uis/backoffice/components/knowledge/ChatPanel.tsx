"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { AlertCircle, ArrowUp, Loader2, MessageSquarePlus, Sparkles, X } from "lucide-react";
import { agentError, createChatSession, getChatSession, listChatSessions } from "@/lib/agents/api";
import type { AgentRoute, ChatMessage, ChatSession } from "@/lib/agents/types";
import { useChatPanel } from "@/lib/chat/panel-context";
import { ChatSocketClient } from "@/lib/realtime/chat";
import type { ChatConnectionState, ChatSocketEvent } from "@/lib/realtime/chat";

const ROUTES: { value: AgentRoute; label: string; description: string }[] = [
  { value: "auto", label: "Auto", description: "Let the CX agent choose the best source" },
  { value: "knowledge", label: "Knowledge base", description: "Use policies, SLAs, and procedures" },
  { value: "ticket", label: "Ticket lookup", description: "Use a specific ticket or order number" },
];

type Status = "idle" | "creating_session" | "awaiting_acknowledgement" | "generating" | "error";
type ViewportRect = { top: number; left: number; width: number | string; height: number | string };
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

// The Engagement 10 chat client, relocated verbatim from AskKnowledgeBox and mounted once in the
// protected layout so "Ask AI" opens it from any route. Opening creates no server state.
// How far from the bottom the reader may be before auto-follow stops fighting them.
const FOLLOW_THRESHOLD_PX = 80;

function isTurnActive(status: Status): boolean {
  return status === "creating_session" || status === "awaiting_acknowledgement" || status === "generating";
}

/** True on touch-primary devices, where an on-screen keyboard covers the transcript. */
function hasOnScreenKeyboard(): boolean {
  // Guarded rather than assumed: matchMedia is absent in jsdom, and a missing
  // capability should degrade to desktop behaviour rather than throw mid-render.
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false;
  return window.matchMedia("(pointer: coarse)").matches;
}

export function ChatPanel() {
  const { open, seed, closePanel } = useChatPanel();
  const [panelQuestion, setPanelQuestion] = useState("");
  const [route, setRoute] = useState<AgentRoute>("auto");
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSession, setActiveSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [connectionState, setConnectionState] = useState<ChatConnectionState>("disconnected");
  const panelInputRef = useRef<HTMLTextAreaElement>(null);
  const messagesRef = useRef<HTMLDivElement>(null);
  const socketRef = useRef<ChatSocketClient | null>(null);
  const tokenSequencesRef = useRef<Record<string, number>>({});
  const pendingQuestionRef = useRef<string | null>(null);
  const activeGenerationIdRef = useRef<string | null>(null);
  const seedNonceRef = useRef<number | null>(null);
  const openHandledRef = useRef(false);
  const wasOpenRef = useRef(false);
  const [viewportRect, setViewportRect] = useState<ViewportRect>({
    top: 0,
    left: 0,
    width: "100vw",
    height: "100dvh",
  });

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
      activeGenerationIdRef.current = generationId;
      const base: DisplayMessage[] = generationId && partial
        ? [...snapshotMessages, {
            message_id: `stream-${generationId}`,
            role: "assistant",
            content: partial,
            interrupted: false,
          }]
        : snapshotMessages;
      // A snapshot for a session created moments ago is empty: the question is still
      // in flight and has not been persisted yet. Replacing state wholesale would
      // erase the message the sender is looking at, show the empty state, then bring
      // it back when `user_message` lands. Carry forward anything the server has not
      // acknowledged instead.
      let carried: DisplayMessage[] = [];
      setMessages((current) => {
        carried = current.filter(
          (row) =>
            row.message_id.startsWith("pending-user-") &&
            !base.some((row2) => row2.role === "user" && row2.content === row.content),
        );
        return carried.length ? [...base, ...carried] : base;
      });
      // Likewise, do not drop back to idle while a question is still unacknowledged;
      // that flickers the "responding" indicator off and on.
      setStatus((current) => {
        if (generationId) return "generating";
        return isTurnActive(current) ? current : "idle";
      });
      setErrorMessage("");
      return;
    }
    if (event === "user_message" && data.message && typeof data.message === "object") {
      const message = data.message as unknown as ChatMessage;
      const generationId = typeof data.generation_id === "string" ? data.generation_id : null;
      activeGenerationIdRef.current = generationId;
      if (pendingQuestionRef.current === message.content) pendingQuestionRef.current = null;
      setMessages((current) => {
        if (current.some((row) => row.message_id === message.message_id)) return current;
        const pending = current.findIndex(
          (row) => row.role === "user" && row.message_id.startsWith("pending-user-") && row.content === message.content,
        );
        if (pending < 0) return [...current, message];
        return current.map((row, index) => index === pending ? message : row);
      });
      setStatus("generating");
      return;
    }
    const generationId = typeof data.generation_id === "string" ? data.generation_id : "unknown";
    const draftId = `stream-${generationId}`;
    if (event === "token_chunk" && typeof data.token === "string") {
      const sequence = typeof data.sequence === "number" ? data.sequence : 0;
      if (sequence && sequence <= (tokenSequencesRef.current[generationId] ?? 0)) return;
      if (sequence) tokenSequencesRef.current[generationId] = sequence;
      activeGenerationIdRef.current = generationId;
      setStatus("generating");
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
      const completesActiveTurn = activeGenerationIdRef.current === generationId;
      if (completesActiveTurn) activeGenerationIdRef.current = null;
      const messageId = typeof data.message_id === "string" ? data.message_id : draftId;
      const routeTaken = typeof data.route_taken === "string" ? data.route_taken : undefined;
      // Prefer the server's stored answer over the accumulated deltas. An output
      // guardrail that fires mid-stream has already emitted the tokens preceding it,
      // so trusting the accumulation would leave the blocked content on screen with
      // the refusal appended to it.
      const authoritative = typeof data.answer === "string" ? data.answer : undefined;
      setMessages((current) => current.map((row) => row.message_id === draftId
        ? { ...row, message_id: messageId, route_taken: routeTaken, ...(authoritative ? { content: authoritative } : {}) }
        : row));
      if (completesActiveTurn) {
        setStatus(pendingQuestionRef.current ? "awaiting_acknowledgement" : "idle");
      }
      void refreshSessions();
      return;
    }
    if (event === "generation_interrupted") {
      delete tokenSequencesRef.current[generationId];
      const interruptsActiveTurn = activeGenerationIdRef.current === generationId;
      if (interruptsActiveTurn) activeGenerationIdRef.current = null;
      const messageId = typeof data.message_id === "string" ? data.message_id : draftId;
      setMessages((current) => current.map((row) => row.message_id === draftId
        ? { ...row, message_id: messageId, interrupted: true }
        : row));
      if (interruptsActiveTurn) {
        setStatus(pendingQuestionRef.current ? "awaiting_acknowledgement" : "idle");
      }
      void refreshSessions();
      return;
    }
    if (event === "generation_failed") {
      // Legacy failure frames may omit generation_id; accept those as terminal.
      // When an id is present, a delayed failure from a redirected generation
      // must not terminate the newer active turn.
      if (typeof data.generation_id === "string" && activeGenerationIdRef.current !== generationId) return;
      pendingQuestionRef.current = null;
      activeGenerationIdRef.current = null;
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

  const submit = useCallback(async (raw: string, routeOverride?: AgentRoute) => {
    const trimmed = raw.trim();
    if (!trimmed || status === "creating_session") return;
    const activeRoute = routeOverride ?? route;
    const redirecting = isTurnActive(status);

    setPanelQuestion("");
    pendingQuestionRef.current = trimmed;
    setStatus(activeSession ? "awaiting_acknowledgement" : "creating_session");
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
      if (redirecting) {
        socket.interrupt(trimmed, activeRoute);
      } else {
        socket.sendUserMessage(trimmed, activeRoute);
      }
      setStatus("awaiting_acknowledgement");
      if (hasOnScreenKeyboard()) panelInputRef.current?.blur();
    } catch (error) {
      pendingQuestionRef.current = null;
      activeGenerationIdRef.current = null;
      setErrorMessage(agentError(error).message);
      setStatus("error");
    }
  }, [activeSession, connectSession, route, status]);

  // Lock the page behind the dialog while it is open.
  //
  // Without this the document keeps scrolling under the panel, and on iOS the
  // browser scrolls the document to reveal the focused composer when the keyboard
  // opens -- which slid the fixed overlay up and exposed a strip of the Back Office
  // beneath it. Position-fixing the body pins the page and preserves the reader's
  // place, which `overflow: hidden` alone does not do on iOS.
  useLayoutEffect(() => {
    if (!open) return;
    const { body } = document;
    const scrollY = window.scrollY;
    const previous = {
      position: body.style.position,
      top: body.style.top,
      left: body.style.left,
      right: body.style.right,
      overflow: body.style.overflow,
    };
    body.style.position = "fixed";
    body.style.top = `-${scrollY}px`;
    body.style.left = "0";
    body.style.right = "0";
    body.style.overflow = "hidden";
    return () => {
      body.style.position = previous.position;
      body.style.top = previous.top;
      body.style.left = previous.left;
      body.style.right = previous.right;
      body.style.overflow = previous.overflow;
      window.scrollTo(0, scrollY);
    };
  }, [open]);

  // Pin the entire overlay to the visual viewport. On iOS the keyboard can both
  // shrink and pan that viewport while leaving the layout viewport unchanged, so
  // height alone still leaves the fixed panel above the visible screen.
  useLayoutEffect(() => {
    if (!open) return;
    const viewport = window.visualViewport;
    let firstFrame = 0;
    let secondFrame = 0;
    const readViewport = () => {
      setViewportRect(viewport ? {
        top: viewport.offsetTop,
        left: viewport.offsetLeft,
        width: viewport.width,
        height: viewport.height,
      } : {
        top: 0,
        left: 0,
        width: window.innerWidth,
        height: window.innerHeight,
      });
    };
    const sync = () => {
      window.cancelAnimationFrame(firstFrame);
      window.cancelAnimationFrame(secondFrame);
      firstFrame = window.requestAnimationFrame(() => {
        readViewport();
        // WebKit may publish its corrected offset one frame after resize/scroll.
        secondFrame = window.requestAnimationFrame(readViewport);
      });
    };
    sync();
    viewport?.addEventListener("resize", sync);
    viewport?.addEventListener("scroll", sync);
    viewport?.addEventListener("scrollend", sync);
    window.addEventListener("orientationchange", sync);
    window.addEventListener("focusin", sync);
    window.addEventListener("focusout", sync);
    return () => {
      window.cancelAnimationFrame(firstFrame);
      window.cancelAnimationFrame(secondFrame);
      viewport?.removeEventListener("resize", sync);
      viewport?.removeEventListener("scroll", sync);
      viewport?.removeEventListener("scrollend", sync);
      window.removeEventListener("orientationchange", sync);
      window.removeEventListener("focusin", sync);
      window.removeEventListener("focusout", sync);
      setViewportRect({ top: 0, left: 0, width: "100vw", height: "100dvh" });
    };
  }, [open]);

  // Keep the transcript pinned to the latest message (on open, on new tokens, on session load).
  //
  // `messages` changes on every streamed token, so writing scrollTop directly here
  // forced a synchronous layout on each one -- visible as jank while the agent
  // responds. The write is now coalesced into one animation frame, and it is skipped
  // when the reader has deliberately scrolled up, which previously yanked them back
  // to the bottom token by token and made the transcript unreadable mid-stream.
  useEffect(() => {
    const node = messagesRef.current;
    const justOpened = open && !wasOpenRef.current;
    wasOpenRef.current = open;
    if (!node || !open) return;
    const distanceFromBottom = node.scrollHeight - node.scrollTop - node.clientHeight;
    if (!justOpened && distanceFromBottom > FOLLOW_THRESHOLD_PX) return;
    const frame = window.requestAnimationFrame(() => {
      node.scrollTop = node.scrollHeight;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [messages, open]);

  // Focus the composer and wire Escape-to-close while the panel is open.
  useEffect(() => {
    if (!open) return;
    if (!hasOnScreenKeyboard()) panelInputRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") closePanel();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [open, closePanel]);

  // Submit a seed question forwarded from the home Ask box (once per seed nonce). Deferred out of the
  // effect body so it does not setState synchronously within the effect.
  useEffect(() => {
    if (!open || !seed || seedNonceRef.current === seed.nonce) return;
    seedNonceRef.current = seed.nonce;
    openHandledRef.current = true; // this open is a seeded question; skip auto-load
    const seededRoute = seed.route as AgentRoute | undefined;
    queueMicrotask(() => {
      if (seededRoute) setRoute(seededRoute); // reflect the hero's route choice in the panel selector
      void submit(seed.question, seededRoute);
    });
  }, [open, seed, submit]);

  const openSession = useCallback(async (sessionId: string) => {
    if (!sessionId) return;
    pendingQuestionRef.current = null;
    activeGenerationIdRef.current = null;
    setStatus("creating_session");
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
  }, [connectSession]);

  // On a plain open (no fresh seed), show the most recent conversation if one exists (a read, not a
  // write). A fresh seed question is handled by the seed effect above, which claims openHandledRef.
  useEffect(() => {
    if (!open) {
      openHandledRef.current = false;
      return;
    }
    if (openHandledRef.current) return;
    openHandledRef.current = true;
    if (!activeSession && sessions.length > 0) {
      const id = sessions[0].session_id;
      queueMicrotask(() => void openSession(id));
    }
  }, [open, sessions, activeSession, openSession]);

  function startNewChat() {
    socketRef.current?.close();
    socketRef.current = null;
    setActiveSession(null);
    setMessages([]);
    setErrorMessage("");
    setStatus("idle");
    setConnectionState("disconnected");
    pendingQuestionRef.current = null;
    activeGenerationIdRef.current = null;
  }

  const selectedRoute = ROUTES.find((option) => option.value === route) ?? ROUTES[0];

  if (!open) return null;

  return (
    <div className="fixed z-50 overflow-hidden" style={{
      top: viewportRect.top,
      left: viewportRect.left,
      width: viewportRect.width,
      height: viewportRect.height,
    }}>
      <button type="button" aria-label="Close chat" onClick={closePanel} className="absolute inset-0 bg-navy-deep/35 backdrop-blur-[1px]" />
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="chat-panel-title"
        className="absolute inset-0 flex overflow-hidden bg-white shadow-2xl dark:bg-ink-900 sm:inset-y-0 sm:left-auto sm:right-0 sm:w-[min(48rem,calc(100vw-2rem))] sm:border-l sm:border-mist dark:sm:border-ink-600"
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
          <header className="flex items-center justify-between gap-3 border-b border-mist px-4 pb-3 pt-[calc(0.75rem+env(safe-area-inset-top))] dark:border-ink-600 sm:px-5 sm:py-3">
            <div className="min-w-0">
              <h2 id="chat-panel-title" className="truncate font-black text-navy-deep dark:text-neutral-100">First-line CX agent</h2>
              <p className="truncate text-xs text-neutral-400">
                {selectedRoute.label} route · {connectionState === "reconnecting" ? "reconnecting…" : connectionState}
              </p>
            </div>
            <button type="button" onClick={closePanel} aria-label="Close chat" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-mist text-navy hover:bg-ivory dark:border-ink-600 dark:text-neutral-100 dark:hover:bg-ink-700">
              <X className="h-5 w-5" aria-hidden="true" />
            </button>
          </header>

          <div className="border-b border-mist px-4 py-2 dark:border-ink-600 md:hidden">
            <div className="flex items-center gap-2">
              <button type="button" onClick={startNewChat} className="shrink-0 rounded-lg bg-navy px-3 py-2 text-xs font-bold text-white dark:bg-sky">New chat</button>
              <label htmlFor="mobile-chat-history" className="sr-only">Conversation history</label>
              <select id="mobile-chat-history" value={activeSession?.session_id ?? ""} onChange={(event) => void openSession(event.target.value)} className="min-w-0 flex-1 rounded-lg border border-mist bg-white px-2 py-2 text-base text-navy sm:text-xs dark:border-ink-600 dark:bg-ink-800 dark:text-neutral-100">
                <option value="">Conversation history</option>
                {sessions.map((session) => <option key={session.session_id} value={session.session_id}>{sessionLabel(session)}</option>)}
              </select>
            </div>
          </div>

          <div ref={messagesRef} aria-live="polite" className="flex-1 space-y-4 overflow-y-auto overscroll-contain px-4 py-5 sm:px-6">
            {!messages.length && !isTurnActive(status) ? (
              <div className="mx-auto mt-12 max-w-sm text-center">
                <Sparkles className="mx-auto mb-3 h-8 w-8 text-sky" aria-hidden="true" />
                <p className="font-black text-navy-deep dark:text-neutral-100">How can I help?</p>
                <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-300">Ask about returns, delivery policy, carriers, or a specific ticket.</p>
              </div>
            ) : null}
            {messages.map((message) => (
              <div key={message.message_id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${message.role === "user" ? "bg-navy text-white dark:bg-sky" : "border border-mist bg-neutral-50 text-navy-deep dark:border-ink-600 dark:bg-ink-800 dark:text-neutral-100"}`}>
                  <p className="whitespace-pre-wrap break-words">{message.content}</p>
                  {message.route_taken ? <p className="mt-2 text-[0.68rem] font-bold uppercase tracking-wide text-neutral-400">Via {routeLabel(message.route_taken)}</p> : null}
                  {message.interrupted ? <p className="mt-2 text-xs italic text-coral">Response interrupted</p> : null}
                </div>
              </div>
            ))}
            {status === "creating_session" ? <div className="flex items-center gap-2 text-sm text-neutral-400"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Connecting&hellip;</div> : null}
            {status === "awaiting_acknowledgement" || status === "generating" ? <div className="flex items-center justify-between gap-3 text-sm text-neutral-400"><span className="flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Agent is responding&hellip;</span><button type="button" onClick={() => socketRef.current?.interrupt(null, route)} className="rounded-lg border border-coral/50 px-3 py-1.5 text-xs font-bold text-coral hover:bg-coral/10">Stop response</button></div> : null}
            {status === "error" ? <div role="alert" className="flex items-start gap-2 rounded-xl border border-coral/40 bg-coral/10 px-4 py-3 text-sm text-coral"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /><span>{errorMessage}</span></div> : null}
          </div>

          <form onSubmit={(event) => { event.preventDefault(); void submit(panelQuestion); }} className="border-t border-mist px-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] pt-3 dark:border-ink-600 sm:p-4">
            <div className="mb-2 flex items-center gap-2">
              <label htmlFor="panel-agent-route" className="text-xs font-bold text-neutral-500 dark:text-neutral-300">Agent route</label>
              <select id="panel-agent-route" value={route} onChange={(event) => setRoute(event.target.value as AgentRoute)} className="min-w-0 flex-1 rounded-lg border border-mist bg-white px-2 py-1.5 text-base font-bold text-navy sm:flex-none sm:text-xs dark:border-ink-600 dark:bg-ink-800 dark:text-neutral-100">
                {ROUTES.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </div>
            <div className="flex items-end gap-2 rounded-xl border border-mist bg-neutral-50 p-2 focus-within:border-sky dark:border-ink-600 dark:bg-ink-800">
              <label htmlFor="chat-panel-question" className="sr-only">Send a message</label>
              <textarea ref={panelInputRef} id="chat-panel-question" value={panelQuestion} onChange={(event) => setPanelQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void submit(panelQuestion); } }} rows={2} placeholder="Send a message" className="min-h-[2.75rem] min-w-0 flex-1 resize-none bg-transparent px-2 py-1.5 text-base text-navy-deep outline-none sm:text-sm dark:text-neutral-100" />
              <button type="submit" disabled={status === "creating_session" || !panelQuestion.trim()} aria-label={isTurnActive(status) ? "Interrupt and redirect" : "Send message"} className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-navy text-white disabled:opacity-40 dark:bg-sky">
                {status === "creating_session" ? <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" /> : <ArrowUp className="h-5 w-5" aria-hidden="true" />}
              </button>
            </div>
          </form>
        </div>
      </section>
    </div>
  );
}
