import { Bot, Cable, GaugeCircle, NotebookPen } from "lucide-react";

const CAPABILITIES = [
  {
    title: "Token & cost analytics",
    description: "Track token usage, latency and spend per agent and per tool call.",
    icon: GaugeCircle,
  },
  {
    title: "Tools & connections",
    description: "See which tools and MCP connections each agent can reach, and their health.",
    icon: Cable,
  },
  {
    title: "Agent context",
    description: "Add or update the standing context and instructions that shape each agent.",
    icon: NotebookPen,
  },
];

export default function AgentOsPage() {
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <div className="flex items-center gap-3">
        <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-navy text-white dark:bg-sky">
          <Bot className="h-6 w-6" aria-hidden="true" />
        </span>
        <div>
          <p className="text-xs font-black uppercase tracking-[0.14em] text-teal">Engagements 8–9</p>
          <h1 className="text-2xl font-black text-navy-deep dark:text-neutral-100">Agent OS</h1>
        </div>
      </div>

      <p className="max-w-2xl text-sm text-neutral-500 dark:text-neutral-300">
        Agent OS is the control surface for TrackFlow&rsquo;s AI agents. It builds directly on the RAG
        retrieval and generation functions delivered in Engagement 7. The panels below are planned for
        the agent-engineering and agentic-workflow engagements.
      </p>

      <div className="grid gap-4 sm:grid-cols-3">
        {CAPABILITIES.map((capability) => (
          <div
            key={capability.title}
            className="flex flex-col gap-2 rounded-2xl border border-dashed border-mist bg-white p-5 dark:border-ink-600 dark:bg-ink-800"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-ivory text-navy dark:bg-ink-700 dark:text-neutral-100">
              <capability.icon className="h-5 w-5" aria-hidden="true" />
            </span>
            <h2 className="text-sm font-black text-navy-deep dark:text-neutral-100">{capability.title}</h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-300">{capability.description}</p>
          </div>
        ))}
      </div>

      <p className="rounded-xl border border-mist bg-ivory px-4 py-3 text-xs font-bold text-neutral-500 dark:border-ink-600 dark:bg-ink-800 dark:text-neutral-300">
        Placeholder surface — no agent runtime is wired yet. Tracking: Engagement 8 (agent engineering)
        and Engagement 9 (agentic workflows).
      </p>
    </div>
  );
}
