import { redirect } from "next/navigation";

export default function TelemetryIndexPage() {
  redirect("/backoffice/telemetry/fulfilment");
}
