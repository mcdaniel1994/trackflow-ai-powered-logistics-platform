"use client";

import { FormEvent, useState } from "react";
import { Save } from "lucide-react";
import { errorMessage, patchSupplierRate } from "@/lib/suppliers/api";
import type { Supplier } from "@/lib/suppliers/types";
import { Button } from "@/components/talent/ui/Button";
import { Input } from "@/components/talent/ui/Input";
import { Spinner } from "@/components/talent/ui/Spinner";

type RateUpdateControlProps = {
  supplier: Supplier;
  onUpdated: (supplier: Supplier) => void;
};

function rateInputValue(value: number) {
  return String(value);
}

export function RateUpdateControl({ supplier, onUpdated }: RateUpdateControlProps) {
  const [value, setValue] = useState(() => rateInputValue(supplier.rate_per_shipment));
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  const [syncedSupplier, setSyncedSupplier] = useState(supplier);
  if (syncedSupplier !== supplier) {
    setSyncedSupplier(supplier);
    setValue(rateInputValue(supplier.rate_per_shipment));
    setError("");
  }

  const parsedRate = Number(value);
  const valid = Number.isFinite(parsedRate) && parsedRate > 0;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (!valid) {
      setError("Enter a rate greater than zero.");
      return;
    }

    setPending(true);

    try {
      onUpdated(await patchSupplierRate(supplier.id, { rate_per_shipment: parsedRate }));
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-1">
      <div className="flex min-w-[13rem] items-center gap-2">
        <Input
          aria-label={`Rate for ${supplier.name}`}
          type="number"
          min="0.01"
          step="0.01"
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            setError("");
          }}
          invalid={Boolean(error)}
          disabled={pending}
          className="h-9 w-24"
        />
        <Button type="submit" variant="secondary" disabled={pending || !valid} className="h-9 gap-2 px-3">
          {pending ? (
            <Spinner label="Saving" />
          ) : (
            <>
              <Save className="h-4 w-4" aria-hidden="true" />
              <span>Save</span>
            </>
          )}
        </Button>
      </div>
      {error ? <p className="max-w-[13rem] text-xs font-semibold text-coral">{error}</p> : null}
    </form>
  );
}
