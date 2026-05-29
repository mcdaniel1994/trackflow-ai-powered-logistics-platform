// Form-field wrapper: label + input (passed as children) + helper text.
// Centralizing this keeps spacing and label-input association consistent
// across the whole app, and ensures every input always has a real <label>
// (required for accessibility — clicking the label focuses the input).
//
// `htmlFor` MUST match the child input's `id`. The error/hint also gets a
// derived id so we could wire `aria-describedby` later if we want screen
// readers to announce error text alongside the field.

import type { ReactNode } from "react";

type FieldProps = {
  label: string;
  htmlFor: string;
  error?: string;
  hint?: string;
  children: ReactNode;
};

export function Field({ label, htmlFor, error, hint, children }: FieldProps) {
  const helperId = error ? `${htmlFor}-error` : hint ? `${htmlFor}-hint` : undefined;

  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-semibold text-navy-deep">
        {label}
      </label>
      {children}
      {error ? (
        <p id={helperId} className="text-sm text-coral">
          {error}
        </p>
      ) : hint ? (
        <p id={helperId} className="text-sm text-neutral-500">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
