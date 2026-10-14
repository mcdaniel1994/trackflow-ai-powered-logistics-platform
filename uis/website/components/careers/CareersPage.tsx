"use client";

import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";
import { useLocale } from "@/components/layout/LocaleProvider";
import {
  CAREER_ROLES,
  applicationErrors,
  type CareerRole,
} from "@/lib/careers";
import { getBackOfficeURL } from "@/lib/site-urls";

const COPY = {
  en: {
    title: "Careers at TrackFlow",
    intro:
      "Explore the teams behind our warehouse, delivery and customer support operations.",
    demo: "Portfolio demonstration: these roles are illustrative, not active vacancies. Use fictional information only. Applications go to a shared demo sandbox.",
    apply: "Apply for this role",
    form: "Demo application",
    name: "Fictional full name",
    email: "Demo email (example.com only)",
    role: "Role",
    experience: "Years of experience",
    sample: "Fill sample application",
    acknowledge:
      "I am submitting fictional information for this portfolio demonstration.",
    submit: "Submit demo application",
    pending: "Submitting…",
    success: "Demo application received",
    confirmed:
      "Your candidate record was created in the talent sandbox. Open the Back Office to review it.",
    view: "View in Back Office",
    again: "Start another demo application",
    note: "No CV upload or real contact details are needed.",
    descriptions: [
      "Support executive calendars, travel and coordination.",
      "Help receive inventory, prepare orders and maintain accurate stock.",
      "Help customers with delivery questions, returns policies and support requests.",
    ],
    errors: {
      fictional_name: "Enter a fictional name (up to 100 characters).",
      demo_email: "Use an email ending in @example.com.",
      choose_role: "Select an illustrative role.",
      experience: "Enter a whole number from 0 to 60.",
      acknowledgement: "Confirm that these details are fictional.",
      invalid_fields: "Please review the form.",
    } as Record<string, string>,
    unavailable: "The demo sandbox is unavailable. Please try again later.",
    uncertain:
      "We could not confirm whether the application was saved. Check the Talent Tracker before submitting again.",
    duplicate:
      "The sandbox reports a duplicate application. Check the Talent Tracker.",
  },
  es: {
    title: "Trabaja en TrackFlow",
    intro: "Conoce los equipos de almacén, reparto y atención al cliente.",
    demo: "Demostración de portafolio: estos puestos son ilustrativos, no vacantes reales. Usa solo información ficticia. Las candidaturas se envían a un entorno de demostración compartido.",
    apply: "Solicitar este puesto",
    form: "Candidatura de demostración",
    name: "Nombre completo ficticio",
    email: "Correo de demostración (solo example.com)",
    role: "Puesto",
    experience: "Años de experiencia",
    sample: "Rellenar datos de ejemplo",
    acknowledge:
      "Envío información ficticia para esta demostración de portafolio.",
    submit: "Enviar candidatura de demostración",
    pending: "Enviando…",
    success: "Candidatura de demostración recibida",
    confirmed:
      "El registro se ha creado en el entorno de talento. Abre el Back Office para revisarlo.",
    view: "Ver en Back Office",
    again: "Iniciar otra candidatura",
    note: "No hace falta subir un CV ni datos de contacto reales.",
    descriptions: [
      "Apoya la gestión de agendas, viajes y coordinación ejecutiva.",
      "Ayuda con la recepción de inventario, preparación de pedidos y control de stock.",
      "Ayuda con preguntas de reparto, políticas de devoluciones y solicitudes de soporte.",
    ],
    errors: {
      fictional_name: "Introduce un nombre ficticio (máximo 100 caracteres).",
      demo_email: "Usa un correo que termine en @example.com.",
      choose_role: "Selecciona un puesto ilustrativo.",
      experience: "Introduce un número entero de 0 a 60.",
      acknowledgement: "Confirma que los datos son ficticios.",
      invalid_fields: "Revisa el formulario.",
    } as Record<string, string>,
    unavailable:
      "El entorno de demostración no está disponible. Inténtalo más tarde.",
    uncertain:
      "No pudimos confirmar si se guardó la candidatura. Revisa el gestor de talento antes de volver a enviarla.",
    duplicate:
      "El entorno indica una candidatura duplicada. Revisa el gestor de talento.",
  },
};

export function CareersPage() {
  const { locale } = useLocale();
  const copy = COPY[locale];
  const [values, setValues] = useState({
    full_name: "",
    email: "",
    role: "general" as CareerRole,
    experience_years: "",
    demo_acknowledged: false,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<
    "unavailable" | "uncertain" | "duplicate" | null
  >(null);
  const [savedId, setSavedId] = useState("");
  const inFlight = useRef(false);
  const nameInput = useRef<HTMLInputElement>(null);
  function selectRole(role: CareerRole) {
    setValues((current) => ({ ...current, role }));
    setSavedId("");
    window.setTimeout(() => nameInput.current?.focus(), 0);
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (inFlight.current || failure === "uncertain" || savedId) return;
    const data = {
      ...values,
      experience_years:
        values.experience_years === "" ? NaN : Number(values.experience_years),
    };
    const problems = applicationErrors(data);
    setErrors(problems);
    setFailure(null);
    if (Object.keys(problems).length) return;
    inFlight.current = true;
    setPending(true);
    try {
      const response = await fetch("/api/careers/applications", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
        signal: AbortSignal.timeout(20000),
      });
      const result = await response.json();
      if (
        response.status === 201 &&
        typeof result.candidate_id === "string" &&
        /^[A-Za-z0-9_-]{1,128}$/.test(result.candidate_id)
      )
        setSavedId(result.candidate_id);
      else if (response.status === 422) setErrors(result.fields ?? {});
      else
        setFailure(
          result.code === "uncertain"
            ? "uncertain"
            : result.code === "duplicate"
              ? "duplicate"
              : "unavailable",
        );
    } catch {
      setFailure("uncertain");
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }
  const fieldClass =
    "mt-2 w-full rounded-lg border border-neutral-400 bg-white px-3 py-3 text-base text-navy-deep focus:outline focus:outline-2 focus:outline-coral";
  function error(field: string) {
    return errors[field] ? (
      <p id={`error-${field}`} className="mt-1 text-sm text-red-700">
        {copy.errors[errors[field]] ?? copy.errors.invalid_fields}
      </p>
    ) : null;
  }
  return (
    <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6 lg:py-20">
      <header>
        <p className="text-sm font-bold text-navy">
          TrackFlow · {locale === "es" ? "Demostración" : "Portfolio demo"}
        </p>
        <h1 className="mt-2 text-3xl font-black text-navy-deep sm:text-4xl">
          {copy.title}
        </h1>
        <p className="mt-4 text-lg text-neutral-700">{copy.intro}</p>
        <p className="mt-5 rounded-xl border border-mist bg-ivory p-4 text-sm leading-6 text-navy-deep">
          {copy.demo}
        </p>
      </header>
      <section
        aria-label={copy.role}
        className="my-8 grid gap-4 md:grid-cols-3"
      >
        {(
          [
            "executive_assistant",
            "warehouse_associate",
            "customer_support",
          ] as const
        ).map((role, index) => (
          <article
            key={role}
            className="flex flex-col rounded-xl border border-mist bg-white p-5 shadow-sm"
          >
            <h2 className="text-lg font-bold text-navy-deep">
              {CAREER_ROLES[role][locale]}
            </h2>
            <p className="my-4 flex-1 text-sm leading-6 text-neutral-700">
              {copy.descriptions[index]}
            </p>
            <button
              type="button"
              disabled={pending}
              onClick={() => selectRole(role)}
              className="rounded-lg bg-navy px-4 py-3 text-sm font-bold text-white disabled:opacity-50"
            >
              {copy.apply}
            </button>
          </article>
        ))}
      </section>
      <section
        id="application"
        aria-labelledby="career-form-title"
        className="rounded-2xl border border-mist bg-white p-5 sm:p-8"
      >
        <h2
          id="career-form-title"
          className="text-2xl font-bold text-navy-deep"
        >
          {savedId ? copy.success : copy.form}
        </h2>
        {savedId ? (
          <div role="status" className="mt-4 space-y-4">
            <p>{copy.confirmed}</p>
            <a
              href={`${getBackOfficeURL()}/talent/${encodeURIComponent(savedId)}`}
              className="inline-block rounded-lg bg-navy px-4 py-3 font-bold text-white"
            >
              {copy.view}
            </a>
            <button
              type="button"
              className="block underline"
              onClick={() => {
                setSavedId("");
                setFailure(null);
                setValues({
                  full_name: "",
                  email: "",
                  role: "general",
                  experience_years: "",
                  demo_acknowledged: false,
                });
              }}
            >
              {copy.again}
            </button>
          </div>
        ) : (
          <form onSubmit={submit} className="mt-5 space-y-5" noValidate>
            <p className="text-sm text-neutral-700">{copy.note}</p>
            <button
              type="button"
              disabled={pending}
              onClick={() => {
                setValues((current) => ({
                  ...current,
                  full_name: "Alex Demo",
                  email: `alex.demo.${Date.now()}@example.com`,
                  experience_years: "3",
                  demo_acknowledged: true,
                }));
                setErrors({});
              }}
              className="rounded-lg border border-navy px-4 py-3 text-sm font-bold text-navy"
            >
              {copy.sample}
            </button>
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label htmlFor="career-name" className="font-semibold">
                  {copy.name}
                </label>
                <input
                  ref={nameInput}
                  id="career-name"
                  autoComplete="off"
                  maxLength={100}
                  required
                  disabled={pending}
                  value={values.full_name}
                  onChange={(e) =>
                    setValues({ ...values, full_name: e.target.value })
                  }
                  aria-invalid={!!errors.full_name}
                  aria-describedby={
                    errors.full_name ? "error-full_name" : undefined
                  }
                  className={fieldClass}
                />
                {error("full_name")}
              </div>
              <div>
                <label htmlFor="career-email" className="font-semibold">
                  {copy.email}
                </label>
                <input
                  id="career-email"
                  type="email"
                  autoComplete="off"
                  maxLength={254}
                  required
                  disabled={pending}
                  value={values.email}
                  onChange={(e) =>
                    setValues({ ...values, email: e.target.value })
                  }
                  aria-invalid={!!errors.email}
                  aria-describedby={errors.email ? "error-email" : undefined}
                  className={fieldClass}
                />
                {error("email")}
              </div>
              <div>
                <label htmlFor="career-role" className="font-semibold">
                  {copy.role}
                </label>
                <select
                  id="career-role"
                  disabled={pending}
                  value={values.role}
                  aria-invalid={!!errors.role}
                  aria-describedby={errors.role ? "error-role" : undefined}
                  onChange={(e) =>
                    setValues({ ...values, role: e.target.value as CareerRole })
                  }
                  className={fieldClass}
                >
                  {(Object.keys(CAREER_ROLES) as CareerRole[]).map((role) => (
                    <option key={role} value={role}>
                      {CAREER_ROLES[role][locale]}
                    </option>
                  ))}
                </select>
                {error("role")}
              </div>
              <div>
                <label htmlFor="career-experience" className="font-semibold">
                  {copy.experience}
                </label>
                <input
                  id="career-experience"
                  type="number"
                  min={0}
                  max={60}
                  step={1}
                  required
                  disabled={pending}
                  value={values.experience_years}
                  onChange={(e) =>
                    setValues({ ...values, experience_years: e.target.value })
                  }
                  aria-invalid={!!errors.experience_years}
                  aria-describedby={
                    errors.experience_years
                      ? "error-experience_years"
                      : undefined
                  }
                  className={fieldClass}
                />
                {error("experience_years")}
              </div>
            </div>
            <label className="flex items-start gap-3 text-sm">
              <input
                type="checkbox"
                required
                disabled={pending}
                checked={values.demo_acknowledged}
                onChange={(e) =>
                  setValues({ ...values, demo_acknowledged: e.target.checked })
                }
                className="mt-1 h-5 w-5"
                aria-invalid={!!errors.demo_acknowledged}
                aria-describedby={
                  errors.demo_acknowledged
                    ? "error-demo_acknowledged"
                    : undefined
                }
              />
              {copy.acknowledge}
            </label>
            {error("demo_acknowledged")}
            {Object.keys(errors).length ? (
              <p role="alert" className="text-sm text-red-800">
                {copy.errors.invalid_fields}
              </p>
            ) : null}
            {failure ? (
              <p role="alert" className="rounded-lg bg-red-50 p-3 text-red-800">
                {copy[failure]}
              </p>
            ) : null}
            <button
              type="submit"
              disabled={pending || failure === "uncertain"}
              className="rounded-lg bg-navy px-5 py-3 font-bold text-white disabled:opacity-50"
            >
              {pending ? copy.pending : copy.submit}
            </button>
          </form>
        )}
      </section>
      <div className="mt-6 flex gap-5 text-sm text-navy">
        <Link href="/">{locale === "es" ? "Inicio" : "Home"}</Link>
        <Link href="/privacy">
          {locale === "es" ? "Privacidad" : "Privacy"}
        </Link>
      </div>
    </div>
  );
}
