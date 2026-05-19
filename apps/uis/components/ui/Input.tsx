// Thin wrapper over <input> that applies our standard look and surfaces
// validation state. Passing `invalid` swaps the border to coral AND sets
// `aria-invalid` so screen readers announce the field as erroneous.
// Spreading `...props` means anything <input> supports (type, value, onChange,
// autoComplete, etc.) works as expected.

import type { InputHTMLAttributes } from "react";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  invalid?: boolean;
};

export function Input({ className = "", invalid = false, ...props }: InputProps) {
  return (
    <input
      className={`w-full rounded-md border bg-white px-3 py-2 text-sm text-navy-deep shadow-sm placeholder:text-neutral-500 disabled:cursor-not-allowed disabled:bg-neutral-100 ${
        invalid ? "border-coral" : "border-neutral-300"
      } ${className}`.trim()}
      aria-invalid={invalid || undefined}
      {...props}
    />
  );
}
