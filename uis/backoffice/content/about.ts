/**
 * Content for the About & disclaimers page.
 *
 * Kept as data rather than JSX so the page stays declarative and each list can be
 * asserted in tests without reaching into markup.
 *
 * The license table is curated from the repository's THIRD_PARTY_LICENSES.md and
 * is deliberately not exhaustive: that file documents roughly 650 permissive
 * dependencies it does not enumerate individually. The page says so rather than
 * implying this list is complete.
 */

export type TechGroup = {
  readonly layer: string;
  readonly items: readonly string[];
};

export type LicenseRow = {
  readonly name: string;
  readonly license: string;
  readonly usage: string;
};

export const TECH_STACK: readonly TechGroup[] = [
  {
    layer: "Frontend",
    items: ["Next.js 16 (App Router)", "React 19", "TypeScript", "Tailwind CSS", "lucide-react"],
  },
  {
    layer: "Backend",
    items: ["Python 3.11", "FastAPI", "SQLModel", "Pydantic", "Alembic", "uv"],
  },
  {
    layer: "Data",
    items: [
      "PostgreSQL (Supabase)",
      "Durable job queue with lease and claim-token state machine",
      "Hourly and weekly SQL rollups",
      "Materialized stock balances",
    ],
  },
  {
    layer: "AI",
    items: [
      "LangGraph multi-agent workflows",
      "Retrieval-augmented generation over a policy knowledge base",
      "Qdrant vector store",
      "OpenAI and DeepSeek models",
      "Model Context Protocol (MCP) tool boundary",
    ],
  },
  {
    layer: "Realtime",
    items: ["Server-Sent Events for ticket streams", "WebSocket chat with token streaming"],
  },
  {
    layer: "Infrastructure",
    items: [
      "Docker Compose",
      "Coolify on a self-managed VPS",
      "GitHub Actions with approval-gated deploys",
      "GHCR immutable images",
      "Automatic image rollback on failed release",
    ],
  },
];

export const ARCHITECTURE_NOTES: readonly string[] = [
  "Independent FastAPI services: an identity service owning authentication, a central API owning inventory, incidents, suppliers, reporting, RAG, and the agent workflows, and an MCP server exposing an OAuth-protected tool boundary.",
  "The Back Office is a Next.js app that talks to those services through its own backend-for-frontend routes, so browser code never holds a service credential.",
  "Background work runs as dedicated always-on workers rather than cron jobs, with PostgreSQL as the single dispatch authority.",
  "Releases publish immutable commit-pinned images, run approval-gated migrations, verify readiness, and restore the previous image automatically if a deploy fails.",
];

export const NOTABLE_LICENSES: readonly LicenseRow[] = [
  { name: "FastAPI", license: "MIT", usage: "HTTP framework for every backend service" },
  { name: "SQLModel / SQLAlchemy", license: "MIT", usage: "Persistence and query construction" },
  { name: "Alembic", license: "MIT", usage: "Versioned database migrations" },
  { name: "Pydantic", license: "MIT", usage: "Validation and settings" },
  { name: "LangGraph", license: "MIT", usage: "Agent and multi-agent workflow graphs" },
  { name: "Qdrant", license: "Apache-2.0", usage: "Self-hosted vector store" },
  { name: "Next.js", license: "MIT", usage: "Back Office application framework" },
  { name: "React", license: "MIT", usage: "User interface library" },
  { name: "Tailwind CSS", license: "MIT", usage: "Styling" },
  { name: "lucide-react", license: "ISC", usage: "Icon set" },
  { name: "WeasyPrint", license: "BSD-3-Clause", usage: "Proposal PDF rendering" },
  { name: "pdfminer.six", license: "MIT", usage: "Reading uploaded RFP documents" },
  {
    name: "psycopg / psycopg2",
    license: "LGPL",
    usage: "PostgreSQL drivers, used unmodified as dynamically linked dependencies",
  },
  { name: "certifi", license: "MPL-2.0", usage: "CA certificate bundle" },
];

export const DISCLAIMERS: readonly string[] = [
  "TrackFlow is a portfolio project built to demonstrate full-stack, data, and AI engineering. It is not a real company and provides no real logistics services.",
  "All data in this application is synthetic. Inventory movements, incidents, suppliers, and RFP documents are generated for demonstration and contain no real customer information.",
  "Any prices, delivery commitments, or service levels shown are illustrative. Cost estimates produced by the RFP workflow are drafts for review, not binding quotations.",
  "Named individuals and client brands appearing in the seeded content are fictional.",
  "AI-generated content in this application can be wrong. Every generated proposal section passes through explicit human approval before it forms part of a final document.",
];
