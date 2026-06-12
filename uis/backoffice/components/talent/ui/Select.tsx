// Native <select> styled to match Input. We deliberately use the browser-native
// dropdown rather than a custom one — it's keyboard-accessible by default,
// works on mobile, and avoids the dependency on a UI kit the spec disallows.

import type { SelectHTMLAttributes } from "react";

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  invalid?: boolean;
};

export function Select({ className = "", invalid = false, ...props }: SelectProps) {
  return (
    <select
      className={`w-full rounded-md border bg-white px-3 py-2 text-sm text-navy-deep shadow-sm disabled:cursor-not-allowed disabled:bg-neutral-100 ${
        invalid ? "border-coral" : "border-neutral-300"
      } ${className}`.trim()}
      aria-invalid={invalid || undefined}
      {...props}
    />
  );
}
