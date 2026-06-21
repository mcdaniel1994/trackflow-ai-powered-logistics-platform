"use client";

import { FormEvent, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { KeyRound } from "lucide-react";
import { changePassword } from "@/lib/auth/api";
import { useAuth } from "@/lib/auth/context";
import { errorMessage } from "@/lib/auth/errors";
import { safeNextPath } from "@/lib/auth/redirects";
import { Button } from "@/components/talent/ui/Button";
import { Field } from "@/components/talent/ui/Field";
import { Input } from "@/components/talent/ui/Input";
import { Spinner } from "@/components/talent/ui/Spinner";

export function ChangePasswordForm() {
  const { user, setUser } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [apiError, setApiError] = useState("");
  const [success, setSuccess] = useState("");

  const nextPath = useMemo(() => safeNextPath(searchParams.get("next")), [searchParams]);

  const errors = {
    currentPassword: submitted && !currentPassword ? "Current password is required" : "",
    newPassword:
      submitted && newPassword.length < 8 ? "Use at least 8 characters" : "",
    confirmPassword:
      submitted && confirmPassword !== newPassword ? "Passwords must match" : "",
  };

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
    setApiError("");
    setSuccess("");

    if (!currentPassword || newPassword.length < 8 || confirmPassword !== newPassword) {
      return;
    }

    setPending(true);
    try {
      const updated = await changePassword(currentPassword, newPassword);
      const wasForced = user.must_change_password;
      setUser(updated);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setSubmitted(false);

      if (wasForced) {
        router.replace(nextPath);
        router.refresh();
      } else {
        setSuccess("Password changed.");
      }
    } catch (caught) {
      setApiError(errorMessage(caught));
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="mx-auto max-w-2xl rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-navy-deep">Change password</h2>
      <p className="mt-1 text-sm text-neutral-600">
        Choose a new password with at least 8 characters.
      </p>

      {user.must_change_password ? (
        <div className="mt-5 rounded-md border border-coral/30 bg-coral/10 p-4 text-sm font-semibold text-navy-deep">
          Your temporary password must be changed before you can continue.
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className="mt-5 space-y-4">
        {apiError ? (
          <div className="rounded-md border border-coral/30 bg-coral/10 p-4 text-sm text-navy-deep">
            {apiError}
          </div>
        ) : null}

        {success ? (
          <div className="rounded-md border border-teal/40 bg-teal/10 p-4 text-sm font-semibold text-navy-deep">
            {success}
          </div>
        ) : null}

        <Field label="Current password" htmlFor="current-password" error={errors.currentPassword}>
          <Input
            id="current-password"
            type="password"
            value={currentPassword}
            onChange={(event) => {
              setCurrentPassword(event.target.value);
              setApiError("");
            }}
            autoComplete="current-password"
            invalid={Boolean(errors.currentPassword)}
            disabled={pending}
          />
        </Field>

        <Field label="New password" htmlFor="new-password" error={errors.newPassword}>
          <Input
            id="new-password"
            type="password"
            value={newPassword}
            onChange={(event) => {
              setNewPassword(event.target.value);
              setApiError("");
            }}
            autoComplete="new-password"
            invalid={Boolean(errors.newPassword)}
            disabled={pending}
          />
        </Field>

        <Field label="Confirm new password" htmlFor="confirm-password" error={errors.confirmPassword}>
          <Input
            id="confirm-password"
            type="password"
            value={confirmPassword}
            onChange={(event) => {
              setConfirmPassword(event.target.value);
              setApiError("");
            }}
            autoComplete="new-password"
            invalid={Boolean(errors.confirmPassword)}
            disabled={pending}
          />
        </Field>

        <Button type="submit" className="gap-2" disabled={pending}>
          {pending ? (
            <Spinner label="Saving" className="text-white" />
          ) : (
            <>
              <KeyRound className="h-4 w-4" aria-hidden="true" />
              <span>Change password</span>
            </>
          )}
        </Button>
      </form>
    </section>
  );
}
