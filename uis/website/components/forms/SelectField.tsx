import type { ChangeEventHandler, FocusEventHandler } from "react";

interface SelectOption<TValue extends string> {
  value: TValue;
  label: string;
}

interface SelectFieldProps<TValue extends string> {
  id: string;
  name: string;
  label: string;
  value: TValue | "";
  placeholder: string;
  options: Array<SelectOption<TValue>>;
  onChange: ChangeEventHandler<HTMLSelectElement>;
  onBlur?: FocusEventHandler<HTMLSelectElement>;
  error?: string;
  required?: boolean;
}

export function SelectField<TValue extends string>({
  id,
  name,
  label,
  value,
  placeholder,
  options,
  onChange,
  onBlur,
  error,
  required = false,
}: SelectFieldProps<TValue>) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-black text-neutral-700">
        {label}
        {required ? <span className="ml-1 text-red-700" aria-hidden="true">*</span> : null}
      </label>
      <select
        id={id}
        name={name}
        value={value}
        onChange={onChange}
        onBlur={onBlur}
        required={required}
        aria-required={required}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        className={`mt-1 w-full rounded-md border bg-white px-4 py-3 text-neutral-900 transition focus:border-transparent ${
          error ? "border-red-600" : "border-neutral-300"
        }`}
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error ? (
        <p id={`${id}-error`} className="mt-1 text-sm font-semibold text-red-700" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
