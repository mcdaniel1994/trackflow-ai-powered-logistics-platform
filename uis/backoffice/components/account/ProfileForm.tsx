"use client";

import { FormEvent, useState } from "react";
import { Save } from "lucide-react";
import { updateProfile } from "@/lib/auth/api";
import { useAuth } from "@/lib/auth/context";
import { errorMessage } from "@/lib/auth/errors";
import { Button } from "@/components/talent/ui/Button";
import { Field } from "@/components/talent/ui/Field";
import { Input } from "@/components/talent/ui/Input";
import { Spinner } from "@/components/talent/ui/Spinner";

function formatDate(value: string | null) {
  if (!value) {
    return "Not recorded";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Not recorded";
  }

  return new Intl.DateTimeFormat("en", {
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

export function ProfileForm() {
  const { user, setUser } = useAuth();
  const [name, setName] = useState(user.name);
  const [pending, setPending] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [apiError, setApiError] = useState("");
  const [success, setSuccess] = useState("");

  const nameError = submitted && !name.trim() ? "Name is required" : "";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
    setApiError("");
    setSuccess("");

    if (!name.trim()) {
      return;
    }

    setPending(true);
    try {
      const updated = await updateProfile(user.id, name.trim());
      setUser(updated);
      setName(updated.name);
      setSuccess("Profile updated.");
    } catch (caught) {
      setApiError(errorMessage(caught));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
      <section className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-navy-deep">Profile</h2>
        <p className="mt-1 text-sm text-neutral-600">Update the display name tied to your Back Office account.</p>

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

          <Field label="Name" htmlFor="profile-name" error={nameError}>
            <Input
              id="profile-name"
              value={name}
              onChange={(event) => {
                setName(event.target.value);
                setApiError("");
                setSuccess("");
              }}
              autoComplete="name"
              invalid={Boolean(nameError)}
              disabled={pending}
            />
          </Field>

          <Button type="submit" className="gap-2" disabled={pending || name.trim() === user.name}>
            {pending ? (
              <Spinner label="Saving" className="text-white" />
            ) : (
              <>
                <Save className="h-4 w-4" aria-hidden="true" />
                <span>Save profile</span>
              </>
            )}
          </Button>
        </form>
      </section>

      <aside className="rounded-lg border border-neutral-200 bg-white p-6 text-sm shadow-sm">
        <h2 className="text-lg font-semibold text-navy-deep">Account details</h2>
        <dl className="mt-5 space-y-4">
          <div>
            <dt className="font-semibold text-neutral-500">Email</dt>
            <dd className="mt-1 break-all font-bold text-navy-deep">{user.email}</dd>
          </div>
          <div>
            <dt className="font-semibold text-neutral-500">Role</dt>
            <dd className="mt-1 font-bold capitalize text-navy-deep">{user.role}</dd>
          </div>
          <div>
            <dt className="font-semibold text-neutral-500">Status</dt>
            <dd className="mt-1 font-bold capitalize text-navy-deep">{user.status}</dd>
          </div>
          <div>
            <dt className="font-semibold text-neutral-500">Last login</dt>
            <dd className="mt-1 font-bold text-navy-deep">{formatDate(user.last_login_at)}</dd>
          </div>
        </dl>
      </aside>
    </div>
  );
}
