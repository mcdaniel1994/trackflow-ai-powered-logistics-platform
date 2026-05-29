import type { ChangeEventHandler } from "react";

interface CheckboxFieldProps {
  id: string;
  name: string;
  label: string;
  checked: boolean;
  onChange: ChangeEventHandler<HTMLInputElement>;
  value?: string;
  required?: boolean;
}

export function CheckboxField({
  id,
  name,
  label,
  checked,
  onChange,
  value,
  required = false,
}: CheckboxFieldProps) {
  return (
    <label htmlFor={id} className="flex cursor-pointer items-center gap-3 text-neutral-700">
      <input
        id={id}
        name={name}
        type="checkbox"
        checked={checked}
        onChange={onChange}
        value={value}
        required={required}
        aria-required={required}
        className="h-4 w-4 rounded border-neutral-300 text-coral focus:ring-coral"
      />
      <span>{label}</span>
    </label>
  );
}
