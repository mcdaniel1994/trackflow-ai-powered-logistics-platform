import { Suspense } from "react";
import { InboundOrderForm } from "@/components/inventory/InboundOrderForm";

export default function InboundOrderPage() {
  return <Suspense fallback={<p>Loading receipt form…</p>}><InboundOrderForm /></Suspense>;
}
