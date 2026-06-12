// Candidate form. Used in BOTH places that mutate a candidate:
//   - /candidates/new      (mode="create" -> POST + redirect)
//   - /candidates/[id]     (mode="edit"   -> PATCH + success message)
//
// Keeping one form means: one set of field defs, one validation function, one
// submit/error flow. The `mode` prop is the only behavioral switch.

"use client";

import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { createCandidate, errorFieldErrors, errorMessage, patchCandidate } from "@/lib/talent/api";
import { stageLabel, stageOptions, statusLabel, statusOptions } from "@/lib/talent/labels";
import type { Candidate, CandidateCreate } from "@/lib/talent/types";
import { Button } from "@/components/talent/ui/Button";
import { Field } from "@/components/talent/ui/Field";
import { Input } from "@/components/talent/ui/Input";
import { Select } from "@/components/talent/ui/Select";
import { Spinner } from "@/components/talent/ui/Spinner";

type CandidateFormMode = "create" | "edit";

type CandidateFormProps = {
  mode: CandidateFormMode;
  initial?: Candidate;
  onSaved?: (candidate: Candidate) => void;
};

// Form-state values are all strings — that's what <input> always gives us.
// We coerce types only on submit (e.g. `experience_years` -> Number). Keeping
// them as strings inside the form means we can show whatever the user typed,
// validation messages included, without fighting the input element.
type CandidateFormValues = {
  full_name: string;
  email: string;
  phone: string;
  position: string;
  linkedin_url: string;
  cv_url: string;
  experience_years: string;
  status: string;
  stage: string;
  application_date: string;
};

type ValidationResult = {
  valid: boolean;
  errors: Record<string, string>;
};

function toDateInput(value: string) {
  if (!value) {
    return "";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value.slice(0, 10);
  }

  return date.toISOString().slice(0, 10);
}

function todayInputDate() {
  return new Date().toISOString().slice(0, 10);
}

function initialValues(initial?: Candidate): CandidateFormValues {
  return {
    full_name: initial?.full_name ?? "",
    email: initial?.email ?? "",
    phone: initial?.phone ?? "",
    position: initial?.position ?? "",
    linkedin_url: initial?.linkedin_url ?? "",
    cv_url: initial?.cv_url ?? "",
    experience_years: String(initial?.experience_years ?? 0),
    status: initial?.status ?? statusOptions[0],
    stage: initial?.stage ?? stageOptions[0],
    application_date: toDateInput(initial?.application_date ?? todayInputDate()),
  };
}

function isEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

// Local validation runs on every keystroke (via useMemo below) and returns a
// `{ valid, errors }` object — the same shape used in `packages/shared/`. Errors
// keyed by field name flow straight into the <Field error={...}> components.
//
// We still surface server-side errors too (see `apiFieldErrors` in the component);
// the two get merged before render, with server errors taking precedence so a
// field that passed local validation but failed on the API still shows feedback.
export function validateCandidateForm(values: CandidateFormValues): ValidationResult {
  const errors: Record<string, string> = {};

  for (const field of [
    "full_name",
    "email",
    "phone",
    "position",
    "linkedin_url",
    "cv_url",
    "status",
    "stage",
    "application_date",
  ]) {
    if (!values[field as keyof CandidateFormValues].trim()) {
      errors[field] = "Required";
    }
  }

  if (values.email && !isEmail(values.email)) {
    errors.email = "Enter a valid email address";
  }

  const experience = Number(values.experience_years);

  if (!values.experience_years.trim()) {
    errors.experience_years = "Required";
  } else if (!Number.isFinite(experience) || experience < 0) {
    errors.experience_years = "Enter zero or a positive number";
  }

  return {
    valid: Object.keys(errors).length === 0,
    errors,
  };
}

function valuesToCandidateCreate(values: CandidateFormValues): CandidateCreate {
  return {
    full_name: values.full_name.trim(),
    email: values.email.trim(),
    phone: values.phone.trim(),
    position: values.position.trim(),
    linkedin_url: values.linkedin_url.trim(),
    cv_url: values.cv_url.trim(),
    experience_years: Number(values.experience_years),
    status: values.status as CandidateCreate["status"],
    stage: values.stage as CandidateCreate["stage"],
    application_date: new Date(`${values.application_date}T00:00:00.000Z`).toISOString(),
  };
}

export function CandidateForm({ mode, initial, onSaved }: CandidateFormProps) {
  const router = useRouter();
  const [values, setValues] = useState(() => initialValues(initial));
  const [pending, setPending] = useState(false);
  const [apiError, setApiError] = useState("");
  const [apiFieldErrors, setApiFieldErrors] = useState<Record<string, string>>({});
  const [successMessage, setSuccessMessage] = useState("");

  // Reset the form whenever the parent hands us a different candidate (e.g. the
  // detail page's optimistic select updates replace the record). Adjusting state
  // during render avoids the extra paint a sync-in-effect would cause.
  const [prevInitial, setPrevInitial] = useState(initial);
  if (prevInitial !== initial) {
    setPrevInitial(initial);
    setValues(initialValues(initial));
    setApiError("");
    setApiFieldErrors({});
    setSuccessMessage("");
  }

  const validation = useMemo(() => validateCandidateForm(values), [values]);
  const submitLabel = mode === "create" ? "Register candidate" : "Save changes";

  function updateValue(field: keyof CandidateFormValues, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
    setApiFieldErrors((current) => {
      const next = { ...current };
      delete next[field];
      return next;
    });
  }

  // Submit handler. The flow:
  //   1. Bail early if local validation didn't pass (button is also disabled).
  //   2. Coerce string form values into the typed API payload.
  //   3. POST (create) or PATCH (edit) via lib/api.ts.
  //   4. On success: in create mode, redirect to the new detail page; in edit
  //      mode, stay put and show "Candidate updated." Parent components can
  //      react via `onSaved` (the detail view uses this to refresh its state).
  //   5. On failure: surface a top-of-form banner AND inline per-field errors
  //      pulled from the server response.
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setApiError("");
    setSuccessMessage("");

    if (!validation.valid) {
      return;
    }

    setPending(true);

    try {
      const body = valuesToCandidateCreate(values);
      const saved =
        mode === "create"
          ? await createCandidate(body)
          : await patchCandidate(initial?.id ?? "", body);

      onSaved?.(saved);

      if (mode === "create") {
        router.replace(`/talent/${saved.id}`);
      } else {
        setSuccessMessage("Candidate updated.");
      }
    } catch (requestError) {
      setApiError(errorMessage(requestError));
      setApiFieldErrors(errorFieldErrors(requestError));
    } finally {
      setPending(false);
    }
  }

  const errors = { ...apiFieldErrors, ...validation.errors };
  const disabled = pending || !validation.valid || (mode === "edit" && !initial?.id);

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {apiError ? (
        <div className="rounded-md border border-coral/30 bg-coral/10 p-4 text-sm text-navy-deep">
          <p className="font-semibold">Could not save candidate.</p>
          <p className="mt-1">{apiError}</p>
        </div>
      ) : null}

      {successMessage ? (
        <div className="rounded-md border border-teal/40 bg-teal/10 p-4 text-sm font-semibold text-navy-deep">
          {successMessage}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Full name" htmlFor="full_name" error={errors.full_name}>
          <Input
            id="full_name"
            value={values.full_name}
            onChange={(event) => updateValue("full_name", event.target.value)}
            invalid={Boolean(errors.full_name)}
            disabled={pending}
            autoComplete="name"
          />
        </Field>

        <Field label="Email" htmlFor="email" error={errors.email}>
          <Input
            id="email"
            type="email"
            value={values.email}
            onChange={(event) => updateValue("email", event.target.value)}
            invalid={Boolean(errors.email)}
            disabled={pending}
            autoComplete="email"
          />
        </Field>

        <Field label="Phone" htmlFor="phone" error={errors.phone}>
          <Input
            id="phone"
            value={values.phone}
            onChange={(event) => updateValue("phone", event.target.value)}
            invalid={Boolean(errors.phone)}
            disabled={pending}
            autoComplete="tel"
          />
        </Field>

        <Field label="Position" htmlFor="position" error={errors.position}>
          <Input
            id="position"
            value={values.position}
            onChange={(event) => updateValue("position", event.target.value)}
            invalid={Boolean(errors.position)}
            disabled={pending}
          />
        </Field>

        <Field label="LinkedIn URL" htmlFor="linkedin_url" error={errors.linkedin_url}>
          <Input
            id="linkedin_url"
            type="url"
            value={values.linkedin_url}
            onChange={(event) => updateValue("linkedin_url", event.target.value)}
            invalid={Boolean(errors.linkedin_url)}
            disabled={pending}
          />
        </Field>

        <Field label="CV URL" htmlFor="cv_url" error={errors.cv_url}>
          <Input
            id="cv_url"
            type="url"
            value={values.cv_url}
            onChange={(event) => updateValue("cv_url", event.target.value)}
            invalid={Boolean(errors.cv_url)}
            disabled={pending}
          />
        </Field>

        <Field label="Years of experience" htmlFor="experience_years" error={errors.experience_years}>
          <Input
            id="experience_years"
            type="number"
            min="0"
            value={values.experience_years}
            onChange={(event) => updateValue("experience_years", event.target.value)}
            invalid={Boolean(errors.experience_years)}
            disabled={pending}
          />
        </Field>

        <Field label="Application date" htmlFor="application_date" error={errors.application_date}>
          <Input
            id="application_date"
            type="date"
            value={values.application_date}
            onChange={(event) => updateValue("application_date", event.target.value)}
            invalid={Boolean(errors.application_date)}
            disabled={pending}
          />
        </Field>

        <Field label="Status" htmlFor="candidate_status" error={errors.status}>
          <Select
            id="candidate_status"
            value={values.status}
            onChange={(event) => updateValue("status", event.target.value)}
            invalid={Boolean(errors.status)}
            disabled={pending}
          >
            {statusOptions.map((status) => (
              <option key={status} value={status}>
                {statusLabel(status)}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Stage" htmlFor="candidate_stage" error={errors.stage}>
          <Select
            id="candidate_stage"
            value={values.stage}
            onChange={(event) => updateValue("stage", event.target.value)}
            invalid={Boolean(errors.stage)}
            disabled={pending}
          >
            {stageOptions.map((stage) => (
              <option key={stage} value={stage}>
                {stageLabel(stage)}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={disabled}>
          {pending ? <Spinner label="Saving" className="text-white" /> : submitLabel}
        </Button>
      </div>
    </form>
  );
}
