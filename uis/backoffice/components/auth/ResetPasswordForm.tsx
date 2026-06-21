"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { KeyRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { resetPassword } from "@/lib/auth/api";
import { errorMessage } from "@/lib/auth/errors";
import { Button } from "@/components/talent/ui/Button";
import { Field } from "@/components/talent/ui/Field";
import { Input } from "@/components/talent/ui/Input";
import { Spinner } from "@/components/talent/ui/Spinner";

type ResetPasswordFormProps = {
  token: string;
};

export function ResetPasswordForm({ token }: ResetPasswordFormProps) {
  const router = useRouter();
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [apiError, setApiError] = useState("");

  const missingToken = !token;
  const passwordError = submitted && newPassword.length < 8 ? "Password must be at least 8 characters" : "";
  const confirmError = submitted && newPassword !== confirmPassword ? "Passwords must match" : "";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
    setApiError("");

    if (missingToken || newPassword.length < 8 || newPassword !== confirmPassword) {
      return;
    }

    setPending(true);
    try {
      await resetPassword(token, newPassword);
      router.replace("/login?reset=success");
      router.refresh();
    } catch (caught) {
      setApiError(errorMessage(caught));
    } finally {
      setPending(false);
    }
  }

  if (missingToken) {
    return (
      <div className="space-y-4">
        <div className="rounded-md border border-coral/30 bg-coral/10 p-4 text-sm text-navy-deep">
          This reset link is invalid or expired.
        </div>
        <Link href="/forgot-password" className="text-sm font-semibold text-navy hover:text-coral">
          Request a new reset link
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {apiError ? (
        <div className="space-y-3 rounded-md border border-coral/30 bg-coral/10 p-4 text-sm text-navy-deep">
          <p>{apiError}</p>
          <Link href="/forgot-password" className="font-semibold text-navy hover:text-coral">
            Request a new reset link
          </Link>
        </div>
      ) : null}

      <Field label="New password" htmlFor="reset-password" error={passwordError}>
        <Input
          id="reset-password"
          type="password"
          value={newPassword}
          onChange={(event) => {
            setNewPassword(event.target.value);
            setApiError("");
          }}
          autoComplete="new-password"
          invalid={Boolean(passwordError)}
          disabled={pending}
        />
      </Field>

      <Field label="Confirm password" htmlFor="reset-confirm-password" error={confirmError}>
        <Input
          id="reset-confirm-password"
          type="password"
          value={confirmPassword}
          onChange={(event) => {
            setConfirmPassword(event.target.value);
            setApiError("");
          }}
          autoComplete="new-password"
          invalid={Boolean(confirmError)}
          disabled={pending}
        />
      </Field>

      <Button type="submit" className="w-full gap-2" disabled={pending}>
        {pending ? (
          <Spinner label="Resetting password" className="text-white" />
        ) : (
          <>
            <KeyRound className="h-4 w-4" aria-hidden="true" />
            <span>Reset password</span>
          </>
        )}
      </Button>
    </form>
  );
}
