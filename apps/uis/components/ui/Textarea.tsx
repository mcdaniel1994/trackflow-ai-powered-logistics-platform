// Same pattern as Input/Select but for multi-line text. Currently used only by
// the notes panel; sharing one styled primitive keeps every text surface in the
// app on the same border/padding/focus rules.

import type { TextareaHTMLAttributes } from "react";

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  invalid?: boolean;
};

export function Textarea({ className = "", invalid = false, ...props }: TextareaProps) {
  return (
    <textarea
      className={`w-full rounded-md border bg-white px-3 py-2 text-sm text-navy-deep shadow-sm placeholder:text-neutral-500 disabled:cursor-not-allowed disabled:bg-neutral-100 ${
        invalid ? "border-coral" : "border-neutral-300"
      } ${className}`.trim()}
      aria-invalid={invalid || undefined}
      {...props}
    />
  );
}
