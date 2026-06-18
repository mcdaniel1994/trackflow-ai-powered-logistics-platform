"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useState } from "react";
import { Mail, Power } from "lucide-react";
import {
  errorMessage,
  getSupplierContact,
  patchSupplierStatus,
} from "@/lib/suppliers/api";
import {
  categoryLabel,
  countryLabel,
  statusLabel,
} from "@/lib/suppliers/labels";
import type { Supplier, SupplierContact } from "@/lib/suppliers/types";
import { RateUpdateControl } from "@/components/suppliers/RateUpdateControl";
import { SupplierStatusBadge } from "@/components/suppliers/SupplierStatusBadge";
import { Button, buttonClassName } from "@/components/talent/ui/Button";
import { Spinner } from "@/components/talent/ui/Spinner";

type SupplierDetailViewProps = {
  initialSupplier: Supplier;
};

function formatRate(supplier: Supplier) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: supplier.currency,
  }).format(supplier.rate_per_shipment);
}

function formatDate(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Not recorded";
  }

  return new Intl.DateTimeFormat("en", {
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function DetailItem({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div>
      <dt className="font-semibold text-neutral-500">{label}</dt>
      <dd className="mt-1 text-navy-deep">{children}</dd>
    </div>
  );
}

export function SupplierDetailView({ initialSupplier }: SupplierDetailViewProps) {
  const [supplier, setSupplier] = useState(initialSupplier);
  const [statusPending, setStatusPending] = useState(false);
  const [statusError, setStatusError] = useState("");
  const [statusSuccess, setStatusSuccess] = useState("");
  const [contact, setContact] = useState<SupplierContact | null>(null);
  const [contactPending, setContactPending] = useState(false);
  const [contactError, setContactError] = useState("");

  const nextStatus = supplier.status === "active" ? "suspended" : "active";
  const nextStatusLabel = supplier.status === "active" ? "Suspend supplier" : "Reactivate supplier";

  async function toggleStatus() {
    setStatusPending(true);
    setStatusError("");
    setStatusSuccess("");

    try {
      const updated = await patchSupplierStatus(supplier.id, { status: nextStatus });
      setSupplier(updated);
      setStatusSuccess(`Supplier ${statusLabel(updated.status).toLowerCase()}.`);
    } catch (requestError) {
      setStatusError(errorMessage(requestError));
    } finally {
      setStatusPending(false);
    }
  }

  async function revealContact() {
    setContactPending(true);
    setContactError("");

    try {
      setContact(await getSupplierContact(supplier.id));
    } catch (requestError) {
      setContactError(errorMessage(requestError));
    } finally {
      setContactPending(false);
    }
  }

  return (
    <div className="min-w-0 space-y-6">
      <header className="flex flex-col gap-4 border-b border-mist pb-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <Link href="/suppliers" className="text-sm font-semibold text-navy underline-offset-2 hover:text-coral">
            Back to directory
          </Link>
          <p className="mt-4 text-sm font-semibold uppercase tracking-wide text-coral">Supplier Directory</p>
          <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-center">
            <h1 className="break-words text-2xl font-bold text-navy-deep">{supplier.name}</h1>
            <SupplierStatusBadge status={supplier.status} />
          </div>
          <p className="mt-2 text-sm text-neutral-700">
            {countryLabel(supplier.country)} supplier record for TrackFlow operations.
          </p>
        </div>
        <Link href="/suppliers/new" className={buttonClassName("secondary")}>
          Register supplier
        </Link>
      </header>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          <section className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-navy-deep">Supplier profile</h2>
                <p className="mt-1 text-sm text-neutral-500">
                  Rate last updated {formatDate(supplier.rate_updated_at)}.
                </p>
              </div>
              <div className="text-left md:text-right">
                <p className="text-sm font-semibold text-neutral-500">Current rate</p>
                <p className="mt-1 text-xl font-black text-navy-deep">{formatRate(supplier)}</p>
              </div>
            </div>

            <dl className="mt-6 grid gap-4 text-sm md:grid-cols-2">
              <DetailItem label="Country">{countryLabel(supplier.country)}</DetailItem>
              <DetailItem label="Currency">{supplier.currency}</DetailItem>
              <DetailItem label="Service zone">{supplier.service_zone ?? "Not recorded"}</DetailItem>
              <DetailItem label="Contact">
                {supplier.has_contact_email ? "Contact on file" : "No contact recorded"}
              </DetailItem>
              <div className="md:col-span-2">
                <dt className="font-semibold text-neutral-500">Categories</dt>
                <dd className="mt-2 flex flex-wrap gap-2">
                  {supplier.categories.map((category) => (
                    <span
                      key={category}
                      className="rounded-md bg-mist px-2.5 py-1 text-xs font-semibold text-navy-deep"
                    >
                      {categoryLabel(category)}
                    </span>
                  ))}
                </dd>
              </div>
              <div className="md:col-span-2">
                <dt className="font-semibold text-neutral-500">Notes</dt>
                <dd className="mt-1 whitespace-pre-wrap text-navy-deep">
                  {supplier.notes ?? "No operations notes recorded."}
                </dd>
              </div>
            </dl>
          </section>
        </div>

        <aside className="space-y-6">
          <section className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-navy-deep">Rate and status</h2>
            <p className="mt-1 text-sm text-neutral-500">Operational changes save immediately.</p>

            <div className="mt-5 space-y-5">
              <div>
                <p className="mb-2 text-sm font-semibold text-navy-deep">Rate per shipment</p>
                <RateUpdateControl supplier={supplier} onUpdated={setSupplier} />
              </div>

              <div>
                <p className="mb-2 text-sm font-semibold text-navy-deep">Supplier status</p>
                <Button
                  variant={supplier.status === "active" ? "danger" : "secondary"}
                  onClick={toggleStatus}
                  disabled={statusPending}
                  className="gap-2"
                >
                  {statusPending ? (
                    <Spinner label="Saving" />
                  ) : (
                    <>
                      <Power className="h-4 w-4" aria-hidden="true" />
                      <span>{nextStatusLabel}</span>
                    </>
                  )}
                </Button>
              </div>
            </div>

            {statusError ? (
              <div className="mt-4 rounded-md border border-coral/30 bg-coral/10 p-3 text-sm text-navy-deep">
                {statusError}
              </div>
            ) : null}

            {statusSuccess ? (
              <div className="mt-4 rounded-md border border-teal/40 bg-teal/10 p-3 text-sm font-semibold text-navy-deep">
                {statusSuccess}
              </div>
            ) : null}
          </section>

          <section className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-navy-deep">Contact email</h2>
            <p className="mt-1 text-sm text-neutral-500">
              Contact details are hidden until intentionally revealed.
            </p>

            {contact?.contact_email ? (
              <div className="mt-5 flex min-w-0 flex-col gap-3 sm:flex-row sm:items-center">
                <a
                  href={`mailto:${contact.contact_email}`}
                  className="inline-flex min-w-0 items-center gap-2 break-all text-sm font-semibold text-navy underline-offset-2 hover:text-coral"
                >
                  <Mail className="h-4 w-4 shrink-0" aria-hidden="true" />
                  {contact.contact_email}
                </a>
                <Button
                  variant="ghost"
                  className="w-fit shrink-0 px-2 py-1"
                  aria-label="Hide contact email"
                  onClick={() => {
                    setContact(null);
                    setContactError("");
                  }}
                >
                  Hide
                </Button>
              </div>
            ) : supplier.has_contact_email ? (
              <Button className="mt-5 gap-2" variant="secondary" onClick={revealContact} disabled={contactPending}>
                {contactPending ? (
                  <Spinner label="Loading" />
                ) : (
                  <>
                    <Mail className="h-4 w-4" aria-hidden="true" />
                    <span>Reveal contact email</span>
                  </>
                )}
              </Button>
            ) : (
              <p className="mt-5 text-sm font-semibold text-neutral-600">No contact email recorded.</p>
            )}

            {contact && !contact.contact_email ? (
              <p className="mt-4 text-sm font-semibold text-neutral-600">No contact email recorded.</p>
            ) : null}

            {contactError ? (
              <div className="mt-4 rounded-md border border-coral/30 bg-coral/10 p-3 text-sm text-navy-deep">
                {contactError}
              </div>
            ) : null}
          </section>
        </aside>
      </section>
    </div>
  );
}
