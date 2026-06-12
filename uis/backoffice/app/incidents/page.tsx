import { AppShell } from "@/components/AppShell";
import { IncidentProcessorView } from "@/components/incidents/IncidentProcessorView";

export default function IncidentsPage() {
  return (
    <AppShell>
      <IncidentProcessorView />
    </AppShell>
  );
}

