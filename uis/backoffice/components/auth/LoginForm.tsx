"use client";

import { FormEvent, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { LogIn } from "lucide-react";
import { login } from "@/lib/auth/api";
import { errorMessage } from "@/lib/auth/errors";
import { safeNextPath } from "@/lib/auth/redirects";
import { Button } from "@/components/talent/ui/Button";
import { Field } from "@/components/talent/ui/Field";
import { Input } from "@/components/talent/ui/Input";
import { Spinner } from "@/components/talent/ui/Spinner";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [apiError, setApiError] = useState("");

  const nextPath = useMemo(() => safeNextPath(searchParams.get("next")), [searchParams]);
  const resetSuccess = searchParams.get("reset") === "success";
  const emailError = submitted && !email.trim() ? "Email is required" : "";
  const passwordError = submitted && !password ? "Password is required" : "";

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
