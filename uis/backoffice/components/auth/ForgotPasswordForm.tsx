"use client";

import { FormEvent, useState } from "react";
import { Mail } from "lucide-react";
import { forgotPassword } from "@/lib/auth/api";
import { errorMessage } from "@/lib/auth/errors";
import { Button } from "@/components/talent/ui/Button";
import { Field } from "@/components/talent/ui/Field";
import { Input } from "@/components/talent/ui/Input";
import { Spinner } from "@/components/talent/ui/Spinner";

const PASSWORD_RESET_MESSAGE = "If that address is registered, you'll receive a link shortly.";

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [pending, setPending] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [sent, setSent] = useState(false);
  const [apiError, setApiError] = useState("");

  const emailError = submitted && !email.trim() ? "Email is required" : "";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
    setApiError("");

    if (!email.trim()) {
      return;
    }

    setPending(true);
    try {
      await forgotPassword(email);
      setSent(true);
    } catch (caught) {
      setApiError(errorMessage(caught));
    } finally {
      setPending(false);
    }
  }

  if (sent) {
    return (
      <div className="space-y-4">
        <div className="rounded-md border border-teal/30 bg-teal/10 p-4 text-sm text-navy-deep">
          {PASSWORD_RESET_MESSAGE}
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {apiError ? (
        <div className="rounded-md border border-coral/30 bg-coral/10 p-4 text-sm text-navy-deep">
          {apiError}
        </div>
      ) : null}

      <Field label="Email" htmlFor="forgot-email" error={emailError}>
        <Input
          id="forgot-email"
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

      <Button type="submit" className="w-full gap-2" disabled={pending}>
        {pending ? (
          <Spinner label="Sending link" className="text-white" />
        ) : (
          <>
            <Mail className="h-4 w-4" aria-hidden="true" />
            <span>Send reset link</span>
          </>
        )}
      </Button>
    </form>
  );
}
