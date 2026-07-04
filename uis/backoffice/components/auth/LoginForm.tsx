"use client";

import { FormEvent, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ChevronRight,
  LogIn,
  MousePointerClick,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { login } from "@/lib/auth/api";
import { errorMessage } from "@/lib/auth/errors";
import { safeNextPath } from "@/lib/auth/redirects";
import { Button } from "@/components/talent/ui/Button";
import { Field } from "@/components/talent/ui/Field";
import { Input } from "@/components/talent/ui/Input";
import { Spinner } from "@/components/talent/ui/Spinner";

const DEMO_ACCOUNTS = [
  {
    label: "Admin Demo",
    email: "corymcdaniel01@gmail.com",
    password: "password123",
    Icon: ShieldCheck,
    iconClasses: "bg-coral/10 text-coral",
  },
  {
    label: "Employee Demo",
    email: "employee@trackflow.com",
    password: "password123",
    Icon: UserRound,
    iconClasses: "bg-sky/10 text-sky",
  },
] as const;

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [apiError, setApiError] = useState("");
  const [demoAnnouncement, setDemoAnnouncement] = useState("");

  const nextPath = useMemo(() => safeNextPath(searchParams.get("next")), [searchParams]);
  const resetSuccess = searchParams.get("reset") === "success";
  const emailError = submitted && !email.trim() ? "Email is required" : "";
  const passwordError = submitted && !password ? "Password is required" : "";

  function selectDemoAccount(account: (typeof DEMO_ACCOUNTS)[number]) {
    setEmail(account.email);
    setPassword(account.password);
    setSubmitted(false);
    setApiError("");
    setDemoAnnouncement(`${account.label} credentials filled in.`);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
    setApiError("");

    if (!email.trim() || !password) {
      return;
    }

    setPending(true);
    try {
      const user = await login(email, password);
      const destination = user.must_change_password
        ? `/account/change-password?next=${encodeURIComponent(nextPath)}`
        : nextPath;
      router.replace(destination);
      router.refresh();
    } catch (caught) {
      setApiError(errorMessage(caught));
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {apiError ? (
        <div className="rounded-md border border-coral/30 bg-coral/10 p-4 text-sm text-navy-deep">
          {apiError}
        </div>
      ) : resetSuccess ? (
        <div className="rounded-md border border-teal/30 bg-teal/10 p-4 text-sm text-navy-deep">
          Your password has been reset. Sign in with your new password.
        </div>
      ) : null}

      <section aria-labelledby="demo-credentials-heading" className="space-y-3">
        <div>
          <h2 id="demo-credentials-heading" className="text-lg font-bold text-navy-deep">
            Demo credentials
          </h2>
          <p className="mt-1 text-sm text-neutral-600">
            Click a demo account to autofill the sign-in form.
          </p>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          {DEMO_ACCOUNTS.map(({ Icon, ...account }) => (
            <button
              key={account.email}
              type="button"
              onClick={() => selectDemoAccount({ Icon, ...account })}
              disabled={pending}
              className="group overflow-hidden rounded-lg border border-neutral-300 bg-white text-left shadow-sm transition hover:border-sky hover:shadow-md disabled:cursor-not-allowed disabled:opacity-60"
            >
              <span className="flex items-center gap-3 p-4">
                <span
                  className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full ${account.iconClasses}`}
                >
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-bold text-navy-deep">{account.label}</span>
                  <span className="block break-all text-sm text-neutral-700">{account.email}</span>
                  <span className="mt-0.5 block text-sm text-neutral-600">
                    Password: <span aria-hidden="true">•••••••••••</span>
                    <span className="sr-only">filled automatically</span>
                  </span>
                </span>
                <ChevronRight
                  className="h-5 w-5 shrink-0 text-navy transition-transform group-hover:translate-x-0.5"
                  aria-hidden="true"
                />
              </span>
              <span className="flex items-center justify-center gap-2 border-t border-neutral-200 bg-neutral-50 px-3 py-2 text-sm font-semibold text-neutral-600 group-hover:text-navy">
                <MousePointerClick className="h-4 w-4" aria-hidden="true" />
                Click to autofill
              </span>
            </button>
          ))}
        </div>

        <p className="sr-only" role="status" aria-live="polite">
          {demoAnnouncement}
        </p>
      </section>

      <div className="border-t border-neutral-200" aria-hidden="true" />

      <Field label="Email" htmlFor="login-email" error={emailError}>
        <Input
          id="login-email"
          type="email"
          value={email}
          onChange={(event) => {
            setEmail(event.target.value);
            setApiError("");
          }}
          autoComplete="email"
          invalid={Boolean(emailError)}
          disabled={pending}
          className="!text-base sm:!text-sm"
        />
      </Field>

      <Field label="Password" htmlFor="login-password" error={passwordError}>
        <Input
          id="login-password"
          type="password"
          value={password}
          onChange={(event) => {
            setPassword(event.target.value);
            setApiError("");
          }}
          autoComplete="current-password"
          invalid={Boolean(passwordError)}
          disabled={pending}
          className="!text-base sm:!text-sm"
        />
      </Field>

      <div className="flex justify-end">
        <Link href="/forgot-password" className="text-sm font-semibold text-navy hover:text-coral">
          Forgot your password?
        </Link>
      </div>

      <Button type="submit" className="w-full gap-2" disabled={pending}>
        {pending ? (
          <Spinner label="Signing in" className="text-white" />
        ) : (
          <>
            <LogIn className="h-4 w-4" aria-hidden="true" />
            <span>Sign in</span>
          </>
        )}
      </Button>
    </form>
  );
}
