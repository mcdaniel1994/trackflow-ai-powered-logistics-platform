"use client";

import { useState } from "react";
import { AlertCircle, ArrowUp, Loader2, Sparkles } from "lucide-react";
import { askAgent, agentError } from "@/lib/agents/api";

const SUGGESTIONS = [
  "What's the standard return window?",
  "Which carrier best covers rural Aragón?",
  "Can we promise our delivery SLA on Black Friday?",
  "What is the status of ticket 1?",
];

type Status = "idle" | "loading" | "answered" | "error";

export function AskKnowledgeBox() {
  const [question, setQuestion] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [answer, setAnswer] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [askedQuestion, setAskedQuestion] = useState("");

  async function submit(raw: string) {
    const trimmed = raw.trim();
    if (!trimmed || status === "loading") return;

    setStatus("loading");
    setAskedQuestion(trimmed);
    setAnswer("");
    setErrorMessage("");

    try {
      const result = await askAgent(trimmed);
      setAnswer(result.answer);
      setStatus("answered");
    } catch (error) {
      setErrorMessage(agentError(error).message);
      setStatus("error");
    }
  }

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
          <h2 className="text-base font-black text-navy-deep dark:text-neutral-100">Ask your knowledge base</h2>
          <p className="text-xs text-neutral-500 dark:text-neutral-300">
            Grounded in TrackFlow&rsquo;s policy documents and live ticket status — never invented.
          </p>
        </div>
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submit(question);
        }}
      >
        <div className="flex items-end gap-2 rounded-xl border border-mist bg-neutral-50 p-2 focus-within:border-sky dark:border-ink-600 dark:bg-ink-700">
          <label htmlFor="knowledge-question" className="sr-only">
            Type what you&rsquo;re looking for or ask a question
          </label>
          <textarea
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
            disabled={status === "loading" || !question.trim()}
            aria-label="Ask"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-navy text-white transition hover:bg-navy-deep disabled:cursor-not-allowed disabled:opacity-40 dark:bg-sky dark:hover:bg-teal"
          >
            {status === "loading" ? (
              <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
            ) : (
              <ArrowUp className="h-5 w-5" aria-hidden="true" />
            )}
          </button>
        </div>
      </form>

      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => {
              setQuestion(suggestion);
              void submit(suggestion);
            }}
            className="rounded-full border border-mist bg-white px-3 py-1.5 text-xs font-bold text-navy transition hover:border-sky hover:bg-ivory dark:border-ink-600 dark:bg-ink-700 dark:text-neutral-200 dark:hover:border-sky"
          >
            {suggestion}
          </button>
        ))}
      </div>

      <div aria-live="polite" className="mt-4">
        {status === "loading" ? (
          <div className="flex items-center gap-2 rounded-xl border border-mist bg-neutral-50 px-4 py-3 text-sm text-neutral-500 dark:border-ink-600 dark:bg-ink-700 dark:text-neutral-300">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            Searching the knowledge base&hellip;
          </div>
        ) : null}

        {status === "error" ? (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-xl border border-coral/40 bg-coral/10 px-4 py-3 text-sm text-coral"
          >
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{errorMessage}</span>
          </div>
        ) : null}

        {status === "answered" ? (
          <div className="rounded-xl border border-mist bg-neutral-50 px-4 py-3 dark:border-ink-600 dark:bg-ink-700">
            <p className="mb-1 text-xs font-bold uppercase tracking-wide text-neutral-400">
              {askedQuestion}
            </p>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-navy-deep dark:text-neutral-100">{answer}</p>
          </div>
        ) : null}
      </div>
    </section>
  );
}
