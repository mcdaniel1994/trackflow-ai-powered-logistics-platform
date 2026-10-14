"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { MessageCircle, X } from "lucide-react";
import { useLocale } from "@/components/layout/LocaleProvider";

type Exchange = { question: string; answer: string; outcome: string };
const GREETING =
  /^(?:hi|hello|hey|hola|buenos d[ií]as|buenas tardes|buenas noches|good morning|good afternoon|good evening)[\s!?¡¿.,]*$/i;
const COPY = {
  en: {
    launch: "Chat with TrackFlow",
    title: "TrackFlow Support",
    intro:
      "Ask about coverage, delivery and returns policies. For private tickets or shipment status, contact our team.",
    country: "Policy country",
    choose: "Choose a country",
    us: "United States",
    es: "Spain",
    question: "Your question",
    send: "Send",
    waiting: "Finding an answer…",
    close: "Close support chat",
    contact: "Contact TrackFlow",
    clear: "New conversation",
    error:
      "Support is temporarily unavailable. Please try again later or contact our team.",
    not_enabled:
      "Policy answers have not been enabled in this demo yet. Please contact our team for help.",
    greeting:
      "Hello! Welcome to TrackFlow. Ask about our services, delivery or returns policies. Choose United States or Spain before asking a policy question.",
    busy: "Support is busy. Please try again in a minute.",
    invalid:
      "Please enter a question of up to 1,000 characters and choose a policy country.",
    notice:
      "This chat uses AI to answer public policy questions. Do not share personal details. History clears when you reload this page.",
    you: "You",
  },
  es: {
    launch: "Chatea con TrackFlow",
    title: "Soporte de TrackFlow",
    intro:
      "Pregunta sobre cobertura y políticas de reparto y devoluciones. Para incidencias privadas o seguimiento, contacta con nuestro equipo.",
    country: "País de la política",
    choose: "Elige un país",
    us: "Estados Unidos",
    es: "España",
    question: "Tu pregunta",
    send: "Enviar",
    waiting: "Buscando una respuesta…",
    close: "Cerrar chat de soporte",
    contact: "Contactar con TrackFlow",
    clear: "Nueva conversación",
    error:
      "El soporte no está disponible temporalmente. Inténtalo más tarde o contacta con nuestro equipo.",
    not_enabled:
      "Las respuestas sobre políticas aún no están activadas en esta demostración. Contacta con nuestro equipo para obtener ayuda.",
    greeting:
      "¡Hola! Bienvenido a TrackFlow. Pregunta sobre nuestros servicios y las políticas de reparto o devoluciones. Selecciona Estados Unidos o España antes de consultar una política.",
    busy: "El soporte está ocupado. Inténtalo de nuevo en un minuto.",
    invalid:
      "Introduce una pregunta de hasta 1000 caracteres y selecciona un país.",
    notice:
      "Este chat usa IA para responder preguntas sobre políticas públicas. No compartas datos personales. El historial se borra al recargar la página.",
    you: "Tú",
  },
};
export function SupportChat() {
  const { locale, toggleLocale } = useLocale();
  const copy = COPY[locale];
  const [open, setOpen] = useState(false);
  const [country, setCountry] = useState<"" | "US" | "ES">("");
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<Exchange[]>([]);
  const [pending, setPending] = useState("");
  const [error, setError] = useState<
    "error" | "busy" | "invalid" | "not_enabled" | null
  >(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLElement>(null);
  const countryInput = useRef<HTMLSelectElement>(null);
  const transcript = useRef<HTMLDivElement>(null);
  const inFlight = useRef(false);
  const abort = useRef<AbortController | null>(null);
  function close() {
    setOpen(false);
    trigger.current?.focus();
  }
  useEffect(() => () => abort.current?.abort(), []);
  useEffect(() => {
    const footer = document.querySelector("footer");
    if (!footer) return;
    let frame = 0;
    function measure() {
      frame = 0;
      const overlap = Math.max(
        0,
        window.innerHeight - footer!.getBoundingClientRect().top,
      );
      trigger.current?.style.setProperty(
        "--support-footer-overlap",
        `${overlap}px`,
      );
    }
    function schedule() {
      if (!frame) frame = window.requestAnimationFrame(measure);
    }
    measure();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    const observer =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(schedule);
    observer?.observe(footer);
    observer?.observe(document.body);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      observer?.disconnect();
    };
  }, [locale]);
  useEffect(() => {
    if (!open) return;
    countryInput.current?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function keyboard(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        trigger.current?.focus();
      }
      if (event.key === "Tab") {
        const elements = panel.current?.querySelectorAll<HTMLElement>(
          "button:not(:disabled), a[href], select:not(:disabled), textarea:not(:disabled)",
        );
        if (!elements?.length) return;
        const first = elements[0],
          last = elements[elements.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    }
    document.addEventListener("keydown", keyboard);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", keyboard);
    };
  }, [open]);
  useEffect(() => {
    if (transcript.current)
      transcript.current.scrollTop = transcript.current.scrollHeight;
  }, [history, pending, open]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (inFlight.current) return;
    const text = question.trim();
    if (!text || Array.from(text).length > 1000) {
      setError("invalid");
      return;
    }
    // A static welcome has no policy facts and does not need an AI call or country.
    if (GREETING.test(text)) {
      setHistory((current) => [
        ...current,
        { question: text, answer: copy.greeting, outcome: "clarify" },
      ]);
      setQuestion("");
      setError(null);
      return;
    }
    if (!country) {
      setError("invalid");
      return;
    }
    let context = history
      .slice(-3)
      .filter((item) => item.outcome === "answered")
      .map(({ question, answer }) => ({ question, answer }));
    while (
      context.reduce(
        (sum, item) =>
          sum +
          Array.from(item.question).length +
          Array.from(item.answer).length,
        0,
      ) > 6000
    )
      context = context.slice(1);
    const controller = new AbortController();
    abort.current = controller;
    const timeout = window.setTimeout(() => controller.abort(), 45000);
    inFlight.current = true;
    setPending(text);
    setQuestion("");
    setError(null);
    try {
      const response = await fetch("/api/support/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: text,
          language: locale,
          policy_country: country,
          recent_context: context,
        }),
        signal: controller.signal,
      });
      if (!response.ok) {
        if (response.status === 503) {
          const failure = await response.json().catch(() => null);
          setError(failure?.code === "not_enabled" ? "not_enabled" : "error");
          setQuestion(text);
          return;
        }
        setError(
          response.status === 429
            ? "busy"
            : response.status === 400 || response.status === 422
              ? "invalid"
              : "error",
        );
        setQuestion(text);
        return;
      }
      const data = await response.json();
      if (
        typeof data.answer !== "string" ||
        data.answer.length > 4000 ||
        !["answered", "clarify", "contact", "rejected", "no_context"].includes(
          data.outcome,
        )
      )
        throw new Error("invalid_answer");
      // Only complete, bounded exchanges are carried to the next request.
      setHistory((current) => [
        ...current,
        { question: text, answer: data.answer, outcome: data.outcome },
      ]);
    } catch {
      if (!controller.signal.aborted || abort.current === controller) {
        setError("error");
        setQuestion(text);
      }
    } finally {
      window.clearTimeout(timeout);
      inFlight.current = false;
      setPending("");
    }
  }
  return (
    <>
      <button
        ref={trigger}
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={copy.launch}
        aria-controls="trackflow-support"
        className="fixed bottom-[calc(max(1rem,env(safe-area-inset-bottom))+var(--support-footer-overlap,0px))] right-4 z-40 flex items-center gap-2 rounded-full bg-navy p-4 font-bold text-white shadow-lg focus:outline focus:outline-2 focus:outline-offset-4 focus:outline-navy sm:px-5 sm:py-3"
      >
        <MessageCircle aria-hidden="true" size={20} />
        <span className="hidden sm:inline">{copy.launch}</span>
      </button>
      {open ? (
        <div
          className="fixed inset-0 z-50 bg-navy-deep/40"
          onClick={(event) => {
            if (event.target === event.currentTarget) close();
          }}
        >
          <section
            id="trackflow-support"
            ref={panel}
            role="dialog"
            aria-modal="true"
            aria-labelledby="support-title"
            aria-describedby="support-description"
            className="absolute inset-0 flex flex-col bg-white shadow-2xl sm:bottom-4 sm:left-auto sm:right-4 sm:top-4 sm:w-[min(28rem,calc(100vw-2rem))] sm:rounded-2xl"
          >
            <header className="flex items-start justify-between gap-3 border-b border-mist p-5">
              <div>
                <h2
                  id="support-title"
                  className="text-xl font-black text-navy-deep"
                >
                  {copy.title}
                </h2>
                <p
                  id="support-description"
                  className="mt-2 text-sm text-neutral-700"
                >
                  {copy.intro}
                </p>
              </div>
              <button
                type="button"
                aria-label={copy.close}
                onClick={close}
                className="rounded-lg border border-mist p-3 text-navy"
              >
                <X aria-hidden="true" size={20} />
              </button>
            </header>
            <div className="border-b border-mist px-5 py-3">
              <div className="flex items-center justify-between gap-3">
                <label
                  htmlFor="support-country"
                  className="text-sm font-semibold text-navy"
                >
                  {copy.country}
                </label>
                <button
                  type="button"
                  disabled={!!pending}
                  onClick={toggleLocale}
                  aria-label={
                    locale === "en"
                      ? "Switch support chat to Spanish"
                      : "Cambiar el chat a inglés"
                  }
                  className="rounded border border-mist px-3 py-2 text-sm font-semibold text-navy"
                >
                  {locale === "en" ? "Español" : "English"}
                </button>
              </div>
              <select
                ref={countryInput}
                id="support-country"
                disabled={!!pending}
                value={country}
                onChange={(e) => {
                  setCountry(e.target.value as typeof country);
                  setHistory([]);
                  setError(null);
                }}
                className="mt-2 w-full rounded-lg border border-neutral-400 bg-white px-3 py-2 text-base"
              >
                <option value="">{copy.choose}</option>
                <option value="US">{copy.us}</option>
                <option value="ES">{copy.es}</option>
              </select>
              <button
                type="button"
                disabled={!!pending}
                onClick={() => {
                  setHistory([]);
                  setError(null);
                  setQuestion("");
                }}
                className="mt-2 text-sm font-semibold text-navy underline"
              >
                {copy.clear}
              </button>
            </div>
            <div
              ref={transcript}
              role="log"
              aria-label={copy.title}
              aria-live="polite"
              className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5"
            >
              <p className="text-sm leading-6 text-neutral-700">
                {copy.notice}
              </p>
              {history.map((item, index) => (
                <div key={index} className="space-y-3">
                  <p className="rounded-xl bg-ivory p-3 whitespace-pre-wrap break-words">
                    <span className="sr-only">{copy.you}: </span>
                    {item.question}
                  </p>
                  <p className="rounded-xl border border-mist p-3 whitespace-pre-wrap break-words">
                    <span className="sr-only">{copy.title}: </span>
                    {item.answer}
                  </p>
                </div>
              ))}
              {pending ? (
                <div role="status">
                  <p className="rounded-xl bg-ivory p-3 whitespace-pre-wrap break-words">
                    {pending}
                  </p>
                  <p className="mt-3 text-sm text-neutral-700">
                    {copy.waiting}
                  </p>
                </div>
              ) : null}
              {error ? (
                <p
                  role="alert"
                  className="rounded-xl bg-red-50 p-3 text-sm text-red-800"
                >
                  {copy[error]}
                </p>
              ) : null}
            </div>
            <form
              onSubmit={submit}
              className="space-y-3 border-t border-mist p-5 pb-[max(1.25rem,env(safe-area-inset-bottom))]"
            >
              <label
                htmlFor="support-question"
                className="text-sm font-semibold"
              >
                {copy.question}
              </label>
              <textarea
                id="support-question"
                rows={2}
                maxLength={1000}
                disabled={!!pending}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                className="w-full rounded-lg border border-neutral-400 p-3 text-base"
              />
              <div className="flex items-center justify-between gap-4">
                <Link
                  href="/#contact"
                  onClick={close}
                  className="text-sm text-navy underline"
                >
                  {copy.contact}
                </Link>
                <button
                  type="submit"
                  disabled={!!pending || !question.trim()}
                  className="rounded-lg bg-navy px-5 py-3 font-bold text-white disabled:opacity-50"
                >
                  {copy.send}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </>
  );
}
