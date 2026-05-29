"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useLocale } from "@/components/layout/LocaleProvider";
import type {
  Current3PL,
  LeadFormData,
  LeadFormErrors,
  MonthlyVolume,
  OperatingCountry,
  ProductType,
  ServiceInterest,
} from "@/content/types";
import {
  createEmptyLeadFormData,
  validateLeadField,
  validateLeadForm,
} from "@/lib/leadValidation";
import { CharacterCounter } from "./CharacterCounter";
import { CheckboxField } from "./CheckboxField";
import { SelectField } from "./SelectField";
import { TextField } from "./TextField";

const serviceValues: ServiceInterest[] = ["warehousing", "last-mile", "reverse-logistics"];
const countryValues: Array<Exclude<OperatingCountry, "">> = ["us", "es", "both", "other"];
const productValues: Array<Exclude<ProductType, "">> = [
  "fashion",
  "electronics",
  "cosmetics",
  "food",
  "other",
];
const volumeValues: Array<Exclude<MonthlyVolume, "">> = [
  "0-100",
  "101-500",
  "501-2000",
  "2000+",
  "not-sure",
];
const current3plValues: Array<Exclude<Current3PL, "">> = ["yes", "no", "evaluating"];

export function LeadForm() {
  const { copy } = useLocale();
  const formCopy = copy.application.form;
  const [data, setData] = useState<LeadFormData>(() => createEmptyLeadFormData());
  const [errors, setErrors] = useState<LeadFormErrors>({});
  const [submitted, setSubmitted] = useState(false);
  const comments = data.comments ?? "";

  const options = useMemo(
    () => ({
      countries: countryValues.map((value) => ({ value, label: formCopy.options.countries[value] })),
      products: productValues.map((value) => ({ value, label: formCopy.options.products[value] })),
      volumes: volumeValues.map((value) => ({ value, label: formCopy.options.volumes[value] })),
    }),
    [formCopy],
  );

  function updateField<TKey extends keyof LeadFormData>(field: TKey, value: LeadFormData[TKey]) {
    setData((current) => ({ ...current, [field]: value }));
    setErrors((current) => {
      if (!current[field]) return current;
      const next = { ...current };
      delete next[field];
      return next;
    });
  }

  function validateOne(field: keyof LeadFormData) {
    const error = validateLeadField(field, data, formCopy);
    setErrors((current) => ({ ...current, [field]: error ?? undefined }));
  }

  function toggleService(value: ServiceInterest) {
    const nextServices = data.services.includes(value)
      ? data.services.filter((service) => service !== value)
      : [...data.services, value];
    updateField("services", nextServices);
  }

  return submitted ? (
    <div
      className="rounded-lg border border-teal/50 bg-teal/15 p-8"
      role="alert"
      aria-live="polite"
      aria-atomic="true"
    >
      <h2 className="text-2xl font-black text-navy">{formCopy.success.title}</h2>
      <p className="mt-4 leading-7 text-neutral-700">{formCopy.success.body}</p>
      <p className="mt-4 leading-7 text-neutral-700">
        {formCopy.success.urgent}{" "}
        <a className="font-black text-navy underline" href="mailto:comercial@trackflow.com">
          comercial@trackflow.com
        </a>
      </p>
    </div>
  ) : (
    <form
      noValidate
      className="space-y-8 rounded-lg border border-mist bg-white p-6 shadow-sm sm:p-8"
      onSubmit={(event) => {
        event.preventDefault();
        const nextErrors = validateLeadForm(data, formCopy);
        setErrors(nextErrors);
        if (Object.keys(nextErrors).length === 0) {
          setSubmitted(true);
        }
      }}
    >
      <fieldset className="space-y-6">
        <legend className="w-full border-b border-mist pb-3 text-xl font-black text-navy">
          {formCopy.fieldsets.company}
        </legend>
        <TextField
          id="company-name"
          name="company-name"
          label={formCopy.fields.companyName.label}
          placeholder={formCopy.fields.companyName.placeholder}
          value={data.companyName}
          onChange={(event) => updateField("companyName", event.target.value)}
          onBlur={() => validateOne("companyName")}
          error={errors.companyName}
          autoComplete="organization"
          required
        />
        <TextField
          id="contact-person"
          name="contact-person"
          label={formCopy.fields.contactPerson.label}
          placeholder={formCopy.fields.contactPerson.placeholder}
          value={data.contactPerson}
          onChange={(event) => updateField("contactPerson", event.target.value)}
          onBlur={() => validateOne("contactPerson")}
          error={errors.contactPerson}
          autoComplete="name"
          required
        />
        <TextField
          id="corporate-email"
          name="corporate-email"
          type="email"
          label={formCopy.fields.corporateEmail.label}
          placeholder={formCopy.fields.corporateEmail.placeholder}
          value={data.corporateEmail}
          onChange={(event) => updateField("corporateEmail", event.target.value)}
          onBlur={() => validateOne("corporateEmail")}
          error={errors.corporateEmail}
          autoComplete="email"
          required
        />
        <TextField
          id="phone"
          name="phone"
          type="tel"
          label={formCopy.fields.phone.label}
          placeholder={formCopy.fields.phone.placeholder}
          value={data.phone}
          onChange={(event) => updateField("phone", event.target.value)}
          onBlur={() => validateOne("phone")}
          error={errors.phone}
          autoComplete="tel"
          hint={formCopy.fields.phone.hint}
          required
        />
        <TextField
          id="company-website"
          name="company-website"
          type="url"
          label={formCopy.fields.companyWebsite.label}
          placeholder={formCopy.fields.companyWebsite.placeholder}
          value={data.companyWebsite ?? ""}
          onChange={(event) => updateField("companyWebsite", event.target.value)}
          onBlur={() => validateOne("companyWebsite")}
          error={errors.companyWebsite}
          autoComplete="url"
          optionalLabel={formCopy.optional}
        />
      </fieldset>

      <fieldset className="space-y-6">
        <legend className="w-full border-b border-mist pb-3 text-xl font-black text-navy">
          {formCopy.fieldsets.service}
        </legend>
        <SelectField
          id="operating-country"
          name="operating-country"
          label={formCopy.fields.operatingCountry.label}
          placeholder={formCopy.fields.operatingCountry.placeholder}
          value={data.operatingCountry}
          options={options.countries}
          onChange={(event) => updateField("operatingCountry", event.target.value as OperatingCountry)}
          onBlur={() => validateOne("operatingCountry")}
          error={errors.operatingCountry}
          required
        />
        <SelectField
          id="product-type"
          name="product-type"
          label={formCopy.fields.productType.label}
          placeholder={formCopy.fields.productType.placeholder}
          value={data.productType}
          options={options.products}
          onChange={(event) => updateField("productType", event.target.value as ProductType)}
          onBlur={() => validateOne("productType")}
          error={errors.productType}
          required
        />
        <div>
          <SelectField
            id="monthly-volume"
            name="monthly-volume"
            label={formCopy.fields.monthlyVolume.label}
            placeholder={formCopy.fields.monthlyVolume.placeholder}
            value={data.monthlyVolume}
            options={options.volumes}
            onChange={(event) => updateField("monthlyVolume", event.target.value as MonthlyVolume)}
            onBlur={() => validateOne("monthlyVolume")}
            error={errors.monthlyVolume}
            required
          />
          {data.monthlyVolume === "0-100" ? (
            <p className="mt-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm font-semibold text-amber-800" role="alert">
              {formCopy.lowVolumeWarning}
            </p>
          ) : null}
        </div>
        <div>
          <fieldset>
            <legend className="block text-sm font-black text-neutral-700">
              {formCopy.fields.services.label}
              <span className="ml-1 text-red-700" aria-hidden="true">*</span>
            </legend>
            <div className="mt-3 space-y-2" aria-describedby={errors.services ? "services-error" : undefined}>
              {serviceValues.map((value) => (
                <CheckboxField
                  key={value}
                  id={`service-${value}`}
                  name="services"
                  value={value}
                  label={formCopy.options.services[value]}
                  checked={data.services.includes(value)}
                  onChange={() => toggleService(value)}
                />
              ))}
            </div>
          </fieldset>
          {errors.services ? (
            <p id="services-error" className="mt-1 text-sm font-semibold text-red-700" role="alert">
              {errors.services}
            </p>
          ) : null}
        </div>
        <div>
          <fieldset>
            <legend className="block text-sm font-black text-neutral-700">
              {formCopy.fields.current3pl.label}
              <span className="ml-1 text-red-700" aria-hidden="true">*</span>
            </legend>
            <div
              className="mt-3 space-y-2"
              aria-describedby={errors.current3pl ? "current-3pl-error" : undefined}
            >
              {current3plValues.map((value) => (
                <label key={value} className="flex cursor-pointer items-center gap-3 text-neutral-700">
                  <input
                    type="radio"
                    name="current-3pl"
                    value={value}
                    checked={data.current3pl === value}
                    onChange={() => updateField("current3pl", value)}
                    className="h-4 w-4 border-neutral-300 text-coral focus:ring-coral"
                  />
                  <span>{formCopy.options.current3pl[value]}</span>
                </label>
              ))}
            </div>
          </fieldset>
          {errors.current3pl ? (
            <p id="current-3pl-error" className="mt-1 text-sm font-semibold text-red-700" role="alert">
              {errors.current3pl}
            </p>
          ) : null}
        </div>
        <div>
          <label htmlFor="comments" className="block text-sm font-black text-neutral-700">
            {formCopy.fields.comments.label}
            <span className="ml-2 text-xs font-semibold text-neutral-500">{formCopy.optional}</span>
          </label>
          <textarea
            id="comments"
            name="comments"
            rows={4}
            maxLength={500}
            value={comments}
            placeholder={formCopy.fields.comments.placeholder}
            aria-invalid={Boolean(errors.comments)}
            aria-describedby="comments-counter comments-error"
            onChange={(event) => updateField("comments", event.target.value)}
            onBlur={() => validateOne("comments")}
            className={`mt-1 w-full resize-none rounded-md border px-4 py-3 text-neutral-900 transition focus:border-transparent ${
              errors.comments ? "border-red-600" : "border-neutral-300"
            }`}
          />
          <div className="mt-1 flex items-center justify-between gap-4">
            {errors.comments ? (
              <p id="comments-error" className="text-sm font-semibold text-red-700" role="alert">
                {errors.comments}
              </p>
            ) : (
              <span id="comments-error" />
            )}
            <span id="comments-counter" className="ml-auto">
              <CharacterCounter
                value={comments}
                remainingLabel={formCopy.remaining}
                overLimitLabel={formCopy.overLimit}
              />
            </span>
          </div>
        </div>
        <div>
          <label className="flex cursor-pointer items-start gap-3 text-sm text-neutral-700">
            <input
              id="privacy-policy"
              name="privacy-policy"
              type="checkbox"
              checked={data.privacyPolicy}
              required
              aria-required="true"
              aria-invalid={Boolean(errors.privacyPolicy)}
              aria-describedby={errors.privacyPolicy ? "privacy-policy-error" : undefined}
              onChange={(event) => updateField("privacyPolicy", event.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-neutral-300 text-coral focus:ring-coral"
            />
            <span>
              {formCopy.fields.privacyPolicy.text}{" "}
              <Link href="/privacy" className="font-black text-navy underline">
                {formCopy.fields.privacyPolicy.link}
              </Link>
              <span className="ml-1 text-red-700" aria-hidden="true">*</span>
            </span>
          </label>
          {errors.privacyPolicy ? (
            <p id="privacy-policy-error" className="ml-7 mt-1 text-sm font-semibold text-red-700" role="alert">
              {errors.privacyPolicy}
            </p>
          ) : null}
        </div>
      </fieldset>

      <p className="text-xs text-neutral-500">
        <span className="text-red-700" aria-hidden="true">*</span> {formCopy.requiredNote}
      </p>
      <div className="flex flex-col gap-3 pt-2 sm:flex-row">
        <button
          type="submit"
          className="flex-1 rounded-md bg-navy px-8 py-3 font-black text-white transition hover:bg-coral"
        >
          {formCopy.submit}
        </button>
        <button
          type="button"
          className="rounded-md border border-neutral-300 bg-white px-8 py-3 font-black text-neutral-700 transition hover:bg-ivory"
          onClick={() => {
            setData(createEmptyLeadFormData());
            setErrors({});
          }}
        >
          {formCopy.clear}
        </button>
      </div>
    </form>
  );
}
