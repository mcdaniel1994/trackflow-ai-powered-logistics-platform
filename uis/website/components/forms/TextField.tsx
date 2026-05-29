import type { ChangeEventHandler, FocusEventHandler, HTMLInputTypeAttribute } from "react";

interface TextFieldProps {
  id: string;
  name: string;
  label: string;
  value: string;
  onChange: ChangeEventHandler<HTMLInputElement>;
  onBlur?: FocusEventHandler<HTMLInputElement>;
  placeholder: string;
  error?: string;
  type?: HTMLInputTypeAttribute;
  required?: boolean;
  optionalLabel?: string;
  autoComplete?: string;
  hint?: string;
}

export function TextField({
  id,
  name,
  label,
  value,
  onChange,
  onBlur,
  placeholder,
  error,
  type = "text",
  required = false,
  optionalLabel,
  autoComplete,
  hint,
}: TextFieldProps) {
  const describedBy = [hint ? `${id}-hint` : null, error ? `${id}-error` : null]
    .filter(Boolean)
    .join(" ");

  return (
    <div>
      <label htmlFor={id} className="block text-sm font-black text-neutral-700">
        {label}
        {required ? <span className="ml-1 text-red-700" aria-hidden="true">*</span> : null}
        {!required && optionalLabel ? (
          <span className="ml-2 text-xs font-semibold text-neutral-500">{optionalLabel}</span>
        ) : null}
      </label>
      <input
        id={id}
        name={name}
        type={type}
        value={value}
        onChange={onChange}
        onBlur={onBlur}
        placeholder={placeholder}
        required={required}
        aria-required={required}
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy || undefined}
        autoComplete={autoComplete}
        className={`mt-1 w-full rounded-md border px-4 py-3 text-neutral-900 transition focus:border-transparent ${
          error ? "border-red-600" : "border-neutral-300"
        }`}
      />
      {hint ? (
        <p id={`${id}-hint`} className="mt-1 text-xs text-neutral-500">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={`${id}-error`} className="mt-1 text-sm font-semibold text-red-700" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
