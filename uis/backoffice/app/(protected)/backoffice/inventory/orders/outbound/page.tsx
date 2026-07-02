import { Suspense } from "react";
import { OutboundOrderForm } from "@/components/inventory/OutboundOrderForm";

export default function OutboundOrderPage() {
  return <Suspense fallback={<p>Loading outbound form…</p>}><OutboundOrderForm /></Suspense>;
}
