"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, Clock3, Sparkles } from "lucide-react";
import { listChatSessions } from "@/lib/agents/api";
import type { AgentRoute, ChatSession } from "@/lib/agents/types";
import { useChatPanel } from "@/lib/chat/panel-context";

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

// The home hero box. It opens the shared chat panel (mounted in the protected layout) with the typed
// question in flight; all chat/WebSocket state lives in ChatPanel.
export function AskKnowledgeBox() {
  const { openPanel } = useChatPanel();
  const [question, setQuestion] = useState("");
  const [route, setRoute] = useState<AgentRoute>("auto");
  const [hasHistory, setHasHistory] = useState(false);
  const launcherInputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    let mounted = true;
    void listChatSessions()
      .then((rows: ChatSession[]) => {
        if (mounted) setHasHistory(rows.length > 0);
      })
      .catch(() => {
        // The feature is intentionally off by default.
      });
    return () => {
      mounted = false;
    };
  }, []);

  function ask(value: string) {
    const trimmed = value.trim();
    if (!trimmed) return;
    setQuestion("");
    openPanel(trimmed, route);
  }

  const selectedRoute = ROUTES.find((option) => option.value === route) ?? ROUTES[0];

  return (
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

      <form onSubmit={(event) => { event.preventDefault(); ask(question); }}>
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
                ask(question);
              }
            }}
            rows={2}
            placeholder="Type what you're looking for or ask a question"
            className="min-h-[2.75rem] w-full resize-none bg-transparent px-2 py-1.5 text-sm text-navy-deep outline-none placeholder:text-neutral-400 dark:text-neutral-100 dark:placeholder:text-neutral-500"
          />
          <button
            type="submit"
            disabled={!question.trim()}
            aria-label="Ask"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-navy text-white transition hover:bg-navy-deep disabled:cursor-not-allowed disabled:opacity-40 dark:bg-sky dark:hover:bg-teal"
          >
            <ArrowUp className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
      </form>

      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => ask(suggestion)}
            className="rounded-full border border-mist bg-white px-3 py-1.5 text-xs font-bold text-navy transition hover:border-sky hover:bg-ivory dark:border-ink-600 dark:bg-ink-700 dark:text-neutral-200 dark:hover:border-sky"
          >
            {suggestion}
          </button>
        ))}
      </div>

      {hasHistory ? (
        <button type="button" onClick={() => openPanel()} className="mt-4 inline-flex items-center gap-2 text-xs font-bold text-navy hover:text-sky dark:text-neutral-200">
          <Clock3 className="h-4 w-4" aria-hidden="true" /> Resume recent conversation
        </button>
      ) : null}
    </section>
  );
}
