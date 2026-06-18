"use client";

import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { PlusCircle } from "lucide-react";
import { createSupplier, errorFieldErrors, errorMessage } from "@/lib/suppliers/api";
import {
  categoryLabel,
  categoryOptions,
  countryLabel,
  countryOptions,
  currencyForCountry,
  isCountry,
  statusLabel,
  statusOptions,
} from "@/lib/suppliers/labels";
import type { Country, Status, Supplier, SupplierCategory, SupplierCreate } from "@/lib/suppliers/types";
import { Button } from "@/components/talent/ui/Button";
import { Field } from "@/components/talent/ui/Field";
import { Input } from "@/components/talent/ui/Input";
import { Select } from "@/components/talent/ui/Select";
import { Spinner } from "@/components/talent/ui/Spinner";
import { Textarea } from "@/components/talent/ui/Textarea";

type SupplierFormProps = {
  onCreated?: (supplier: Supplier) => void;
};

type SupplierFormValues = {
  name: string;
  country: Country;
  categories: SupplierCategory[];
  rate_per_shipment: string;
  currency: SupplierCreate["currency"];
  status: Status;
  service_zone: string;
  contact_email: string;
  notes: string;
};

type ValidationResult = {
  valid: boolean;
  errors: Record<string, string>;
};

function emptyValues(): SupplierFormValues {
  const country: Country = "USA";
  return {
    name: "",
    country,
    categories: ["carrier_last_mile"],
    rate_per_shipment: "",
    currency: currencyForCountry(country),
    status: "active",
    service_zone: "",
    contact_email: "",
    notes: "",
  };
}

function isEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function validateSupplierForm(values: SupplierFormValues): ValidationResult {
  const errors: Record<string, string> = {};

  if (!values.name.trim()) {
    errors.name = "Required";
  }

  if (!values.categories.length) {
    errors.categories = "Choose at least one category";
  }

  const rate = Number(values.rate_per_shipment);
  if (!values.rate_per_shipment.trim()) {
    errors.rate_per_shipment = "Required";
  } else if (!Number.isFinite(rate) || rate <= 0) {
    errors.rate_per_shipment = "Enter a rate greater than zero";
  }

  if (values.contact_email.trim() && !isEmail(values.contact_email.trim())) {
    errors.contact_email = "Enter a valid email address";
  }

  return {
    valid: Object.keys(errors).length === 0,
    errors,
  };
}

function optionalText(value: string) {
  return value.trim() || null;
}

function valuesToPayload(values: SupplierFormValues): SupplierCreate {
  return {
    name: values.name.trim(),
    country: values.country,
    categories: values.categories,
    rate_per_shipment: Number(values.rate_per_shipment),
    currency: values.currency,
    status: values.status,
    service_zone: optionalText(values.service_zone),
    contact_email: optionalText(values.contact_email),
    notes: optionalText(values.notes),
  };
}

export function SupplierForm({ onCreated }: SupplierFormProps) {
  const router = useRouter();
  const [values, setValues] = useState(emptyValues);
  const [pending, setPending] = useState(false);
  const [apiError, setApiError] = useState("");
  const [apiFieldErrors, setApiFieldErrors] = useState<Record<string, string>>({});
  const [successMessage, setSuccessMessage] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const validation = useMemo(() => validateSupplierForm(values), [values]);
  const errors = { ...(submitted ? validation.errors : {}), ...apiFieldErrors };

  function updateValue(field: keyof SupplierFormValues, value: string) {
    setValues((current) => {
      if (field === "country" && isCountry(value)) {
        return {
          ...current,
          country: value,
          currency: currencyForCountry(value),
        };
      }

      return { ...current, [field]: value };
    });
    setApiFieldErrors((current) => {
      const next = { ...current };
      delete next[field];
      return next;
    });
  }

  function toggleCategory(category: SupplierCategory, checked: boolean) {
    setValues((current) => ({
      ...current,
      categories: checked
        ? Array.from(new Set([...current.categories, category]))
        : current.categories.filter((value) => value !== category),
    }));
    setApiFieldErrors((current) => {
      const next = { ...current };
      delete next.categories;
      return next;
    });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setApiError("");
    setSuccessMessage("");
    setSubmitted(true);

    if (!validation.valid) {
      return;
    }

    setPending(true);

    try {
      const saved = await createSupplier(valuesToPayload(values));
      onCreated?.(saved);
      setValues(emptyValues());
      setApiFieldErrors({});
      setSubmitted(false);
      setSuccessMessage(`${saved.name} registered.`);
      if (!onCreated) {
        router.replace(`/suppliers/${saved.id}`);
      }
    } catch (requestError) {
      setApiError(errorMessage(requestError));
      setApiFieldErrors(errorFieldErrors(requestError));
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="min-w-0 overflow-hidden rounded-lg border border-neutral-200 bg-white p-5 shadow-sm" aria-labelledby="supplier-form-heading">
      <h2 id="supplier-form-heading" className="text-lg font-semibold text-navy-deep">
        Register supplier
      </h2>

      <form onSubmit={handleSubmit} className="mt-4 space-y-4">
        {apiError ? (
          <div className="rounded-md border border-coral/30 bg-coral/10 p-4 text-sm text-navy-deep">
            <p className="font-semibold">Could not save supplier.</p>
            <p className="mt-1">{apiError}</p>
          </div>
        ) : null}

        {successMessage ? (
          <div className="rounded-md border border-teal/40 bg-teal/10 p-4 text-sm font-semibold text-navy-deep">
            {successMessage}
          </div>
        ) : null}

        <Field label="Supplier name" htmlFor="supplier-name" error={errors.name}>
          <Input
            id="supplier-name"
            value={values.name}
            onChange={(event) => updateValue("name", event.target.value)}
            invalid={Boolean(errors.name)}
            disabled={pending}
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Country" htmlFor="supplier-country" error={errors.country}>
            <Select
              id="supplier-country"
              value={values.country}
              onChange={(event) => updateValue("country", event.target.value)}
              invalid={Boolean(errors.country)}
              disabled={pending}
            >
              {countryOptions.map((country) => (
                <option key={country} value={country}>
                  {countryLabel(country)}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Currency" htmlFor="supplier-currency" error={errors.currency}>
            <Input id="supplier-currency" value={values.currency} readOnly disabled />
          </Field>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Rate per shipment" htmlFor="supplier-rate" error={errors.rate_per_shipment}>
            <Input
              id="supplier-rate"
              type="number"
              min="0.01"
              step="0.01"
              value={values.rate_per_shipment}
              onChange={(event) => updateValue("rate_per_shipment", event.target.value)}
              invalid={Boolean(errors.rate_per_shipment)}
              disabled={pending}
            />
          </Field>

          <Field label="Status" htmlFor="supplier-status" error={errors.status}>
            <Select
              id="supplier-status"
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
        </div>

        <fieldset className="space-y-2">
          <legend className="text-sm font-semibold text-navy-deep">Categories</legend>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            {categoryOptions.map((category) => (
              <label
                key={category}
                className="flex min-w-0 items-start gap-2 rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm font-semibold text-navy-deep"
              >
                <input
                  type="checkbox"
                  checked={values.categories.includes(category)}
                  onChange={(event) => toggleCategory(category, event.target.checked)}
                  disabled={pending}
                  className="mt-0.5 h-4 w-4 shrink-0 rounded border-neutral-300 text-navy"
                />
                <span className="min-w-0 break-words">{categoryLabel(category)}</span>
              </label>
            ))}
          </div>
          {errors.categories ? <p className="text-sm text-coral">{errors.categories}</p> : null}
        </fieldset>

        <Field label="Service zone" htmlFor="supplier-service-zone" error={errors.service_zone}>
          <Input
            id="supplier-service-zone"
            value={values.service_zone}
            onChange={(event) => updateValue("service_zone", event.target.value)}
            invalid={Boolean(errors.service_zone)}
            disabled={pending}
          />
        </Field>

        <Field label="Contact email" htmlFor="supplier-contact-email" error={errors.contact_email}>
          <Input
            id="supplier-contact-email"
            type="email"
            value={values.contact_email}
            onChange={(event) => updateValue("contact_email", event.target.value)}
            invalid={Boolean(errors.contact_email)}
            disabled={pending}
            autoComplete="email"
          />
        </Field>

        <Field label="Notes" htmlFor="supplier-notes" error={errors.notes}>
          <Textarea
            id="supplier-notes"
            value={values.notes}
            onChange={(event) => updateValue("notes", event.target.value)}
            invalid={Boolean(errors.notes)}
            disabled={pending}
            rows={4}
          />
        </Field>

        <Button type="submit" disabled={pending} className="gap-2">
          {pending ? (
            <Spinner label="Saving" className="text-white" />
          ) : (
            <>
              <PlusCircle className="h-4 w-4" aria-hidden="true" />
              <span>Register supplier</span>
            </>
          )}
        </Button>
      </form>
    </section>
  );
}
