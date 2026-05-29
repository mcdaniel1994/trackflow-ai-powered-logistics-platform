# SPEC — TrackFlow · Talent Pipeline Tracker

## Overview

An internal operations tool for TrackFlow's recruiting team. It replaces a shared Excel file currently used by the Zaragoza HQ team to run the **Executive Assistant** hiring pipeline. Three users edit the file concurrently; interview notes have already been overwritten and lost.

This app must feel like a real internal hiring tool — dense, scannable, reliable — not a generic CRUD demo.

The backend (mock API) already exists and is consumed directly from the browser. No backend work is in scope.

Required context: read `docs/briefs/03-talent-pipeline-tracker.md` before implementing. It is the source of truth for stakeholder voice, terminology, and acceptance criteria.

---

## Tech Stack

Use:

- Next.js (latest stable) with the **App Router**
- TypeScript (strict)
- Tailwind CSS (configured inside this app)
- React hooks only — `useState`, `useEffect`, `useTransition`, `useSearchParams`, `useRouter`
- Native `fetch`

Do **not** use:

- Redux, Zustand, Jotai, Recoil
- React Query, SWR
- External UI kits or component libraries (Radix, MUI, Chakra, shadcn, etc.)
- CSS-in-JS libraries

The shared `packages/tailwind-config/` is a CLI pipeline for the static marketing site and is **not** consumed here. This app owns its own `tailwind.config.ts`.

---

## Repository Location

Build inside:

```txt
apps/talent-pipeline-tracker/
```

Initialize a new Next.js application in this directory.

---

## Environment

Create:

```txt
apps/talent-pipeline-tracker/.env.example
```

Required variable:

```env
NEXT_PUBLIC_API_URL=https://playground.4geeks.com/tracker/api/v1
```

Do not commit `.env.local`.

---

## Routes

Three routes. Each one has a single, clear responsibility.

### `/` — Candidate List

- Server component shell + client table.
- Fetch all candidates via `GET /records`.
- Render as a **dense table** (one row per candidate). Columns:
  - Full name
  - Position
  - Status (badge, human-readable label)
  - Stage (chip, human-readable label)
  - Application date
- **Filters** (status, stage) and **search** (name or email) are URL-driven query params (`?status=…&stage=…&q=…`). Updating any filter calls `router.replace` — no full page reload, browser back/forward must restore state.
- Page header reads: **"Executive Assistant — Zaragoza HQ"** plus a **"Register candidate"** button linking to `/candidates/new`.
- Row click navigates to `/candidates/[id]`.
- Empty state ("No candidates match these filters"), loading skeleton, and error banner are all explicit.

### `/candidates/new` — Register Candidate

- Dedicated route. No modal.
- Renders the shared `CandidateForm` in `create` mode.
- All fields required by the API are present; required ones are validated client-side before submit.
- On success: `POST /records` returns the new ID and the user is redirected to `/candidates/[id]`.
- On API failure: error banner above the form; field-level errors inline.

### `/candidates/[id]` — Candidate Detail

- Fetch single candidate (`GET /records/:id`) and its notes (`GET /records/:id/notes`).
- If the ID does not exist: render a friendly not-found view with a "Back to list" link — **never** a stack trace or generic 404.
- Display:
  - full name, email, phone, position
  - LinkedIn URL, CV URL (as external links)
  - years of experience
  - status, stage (labels, never raw API values)
  - application date
- **Status / stage controls:** inline selects that call `PATCH /records/:id` with the changed field only. Show a pending indicator on the control itself; revert and surface an error if the request fails.
- **Edit form:** same `CandidateForm` component as `/candidates/new`, in `edit` mode, prefilled. Submit issues `PATCH /records/:id`.
- **Notes panel:** lists existing notes (newest first), with an inline form to add and a delete button per note. **Deleting a note requires an explicit confirm step** (`window.confirm` is acceptable). This is intentional friction — lost notes are the reason this tool exists.

---

## API Contract

All endpoints are relative to `NEXT_PUBLIC_API_URL`.

| Method | Path | Used by |
|---|---|---|
| GET | `/records` | list page |
| POST | `/records` | `/candidates/new` |
| GET | `/records/:id` | detail page |
| PATCH | `/records/:id` | status/stage control + edit form |
| GET | `/records/:id/notes` | detail page |
| POST | `/records/:id/notes` | notes panel |
| DELETE | `/records/:id/notes/:note_id` | notes panel |

**Use `PATCH` for partial updates.** `PUT` is not used.

Every request must:

- use `async/await`
- show a loading state (skeleton, spinner, or disabled control)
- show a success state where the user needs confirmation
- surface a visible error on non-2xx responses — **never fail silently**

---

## Data Shape

Field names come from the backend. The UI must render exactly what the brief lists. Define these as TypeScript types in `lib/types.ts`:

```ts
type Status = 'received' | 'in_progress' | 'selected' | 'discarded';
type Stage  = 'pending' | 'review' | 'personal_interview' | 'technical_interview' | 'offer_presented';

interface Candidate {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  position: string;
  linkedin_url: string;
  cv_url: string;
  experience_years: number;
  status: Status;
  stage: Stage;
  application_date: string; // ISO date
}

interface Note { id: string; content: string; created_at: string; }
interface APIError { message: string; field_errors?: Record<string, string>; }
```

`CandidatePatch` is `Partial<Candidate>`. `CandidateCreate` is `Omit<Candidate, 'id'>`.

---

## Labels (raw values must never reach the UI)

Centralize label and tone mapping in `lib/labels.ts`.

**Status:**

| API value | UI label | Tone |
|---|---|---|
| `received` | Received | navy (neutral) |
| `in_progress` | In progress | coral (active) |
| `selected` | Selected | green |
| `discarded` | Discarded | slate-muted |

**Stage:**

| API value | UI label |
|---|---|
| `pending` | Pending review |
| `review` | Under review |
| `personal_interview` | Personal interview |
| `technical_interview` | Technical interview |
| `offer_presented` | Offer presented |

Stage is a neutral chip — no per-stage color. Status carries the color signal.

---

## UX Rules

- **URL is the state.** Filters and search live in `searchParams`; refreshing the page restores the view.
- **Loading, success, error are always visible.** Disabled buttons during submit. Inline pending indicator on status/stage controls. Toast or banner on success/failure.
- **Validation runs client-side first.** Required fields, valid email, non-negative experience years. The submit button stays disabled while invalid.
- **Note deletion is confirmed.** A single accidental click must not destroy interview notes.
- **Not-found pages are friendly.** `/candidates/[id]` with a missing ID renders a message and a back link, not a runtime error.
- **Keyboard works everywhere.** Table rows, controls, and form fields are reachable by Tab; focus is visibly outlined; Enter activates the focused row.
- **Accessibility baseline:** semantic HTML (`<table>`, `<th scope="col">`, `<label for>`), form labels associated with inputs, color contrast ≥ WCAG AA, ARIA only where semantics fall short.

---

## Visual Language

This UI is part of the TrackFlow product family. It uses TrackFlow's live **Junecoast** palette — navy primary, coral accent, teal secondary, ivory/mist neutrals — tuned for internal-tool density. The marketing site at [trackflow-ai-powered-logistics-plat.vercel.app](https://trackflow-ai-powered-logistics-plat.vercel.app/) is the visual reference.

**Color tokens** (from `apps/marketing-site/assets/css/styles.css`, `--jc-*` block — these are the values that actually paint the live site):

```ts
navy:      { deep: '#2b486e', DEFAULT: '#2b4d74' }   // text, primary bg
sky:       '#4b7aa6'                                  // secondary blue accent
teal:      '#6ebab8'                                  // soft accent
coral:     '#ed7e4d'                                  // CTA hover, active state, accents
ivory:     '#f0eee6'                                  // warm light surface
mist:      '#e9eef3'                                  // cool light surface / borders
neutral:   { 50:'#f7fafc', 100:'#e9eef3', 200:'#d8e1ea', 300:'#b9c8d8',
             500:'#6f87a5', 600:'#507092', 700:'#3a6088', 900:'#2b486e' }
```

**Usage:**

- Page background: `neutral-50` (`#f7fafc`). Card/table surface: `white`. Subtle borders: `neutral-200` or `mist`.
- Body text: `navy-deep` (`#2b486e`). Secondary text: `neutral-700` (`#3a6088`). Muted/meta: `neutral-500` (`#6f87a5`).
- **Primary action** (submit, "Register candidate"): `bg-navy text-white hover:bg-coral`. This mirrors the marketing site's CTA pattern (navy → coral on hover).
- **Secondary action** (cancel, back): `border border-neutral-300 text-navy hover:bg-mist`.
- Focus ring: `ring-2 ring-coral/55 ring-offset-2` (matches the site's `rgba(237, 126, 77, 0.52)` focus ring).
- Active row / current selection: `bg-ivory`.
- Status badges follow the tone column above (`navy`, `coral`, `green`, `neutral-400`). Stage chips are neutral: `bg-mist text-navy-deep`.
- Links inside content: `text-navy underline-offset-2 hover:text-coral`.

**Typography:** system sans (matches the marketing site). Page titles `text-2xl font-bold`. Section headings `text-lg font-semibold`. Body and table rows `text-sm`. Use `leading-relaxed` only in long-form content (note bodies).

**Density:** internal-tool density, not marketing density.

- Page container: `max-w-7xl mx-auto px-6 py-6`.
- Table row padding: `py-3 px-4`.
- Form field spacing: `space-y-4` within a form; `gap-4` between columns in a two-column layout.
- Card padding: `p-6`.
- Border radius: `rounded-md` on controls and badges, `rounded-lg` on cards and panels.

The result should read as the same product as `apps/marketing-site/` — same navy/coral identity, same shape language — only denser and more operational.

> Note: the marketing site's stylesheet also defines a `--tf-slate-*` / `--tf-gold-*` token set, but those declarations are overridden by the `--jc-*` (Junecoast) block that follows them. Junecoast is the active palette; do not target the slate/gold tokens.

---

## Folder Structure

Keep it flat. This is a small app.

```txt
apps/talent-pipeline-tracker/
├── app/
│   ├── layout.tsx
│   ├── globals.css
│   ├── page.tsx                       # list (/)
│   └── candidates/
│       ├── new/page.tsx               # registration
│       └── [id]/page.tsx              # detail + edit + notes
│
├── components/
│   ├── CandidateTable.tsx
│   ├── CandidateFilters.tsx
│   ├── CandidateForm.tsx              # shared by /new and edit
│   ├── StatusBadge.tsx
│   ├── StageBadge.tsx
│   ├── NotesPanel.tsx
│   ├── NotFound.tsx
│   └── ui/                            # Button, Input, Select, Textarea, Spinner, Field
│
├── lib/
│   ├── api.ts                         # all fetch wrappers — see below
│   ├── labels.ts                      # status/stage maps and tones
│   └── types.ts                       # Candidate, Note, Status, Stage, etc.
│
├── tailwind.config.ts
├── postcss.config.js
├── next.config.ts
├── tsconfig.json
├── package.json
├── .env.example
└── README.md
```

No `hooks/`, `utils/`, `services/`, `styles/` folders. If a helper is small enough to fit in `lib/`, it lives in `lib/`.

---

## Code Organization

**`lib/api.ts`** — the only place `fetch` is called. Reads `NEXT_PUBLIC_API_URL`, throws a typed error on non-2xx, returns parsed JSON. Exports:

```ts
getCandidates(params: { status?: Status; stage?: Stage; q?: string }): Promise<Candidate[]>
getCandidate(id: string): Promise<Candidate>
createCandidate(body: CandidateCreate): Promise<Candidate>
patchCandidate(id: string, body: CandidatePatch): Promise<Candidate>
getNotes(id: string): Promise<Note[]>
createNote(id: string, content: string): Promise<Note>
deleteNote(id: string, noteId: string): Promise<void>
```

Components do not call `fetch` directly.

**`lib/labels.ts`** — `statusLabel(s: Status)`, `stageLabel(s: Stage)`, `statusTone(s: Status)`. The only place raw API values are referenced.

**`lib/types.ts`** — the types from the **Data Shape** section above. No business logic.

**Components:**

- Keep page files thin. A page composes components; it does not contain fetch logic, label maps, or large JSX trees.
- `CandidateForm` is used in two places — write it once, accept a `mode: 'create' | 'edit'` prop and an optional `initial: Candidate`.
- `CandidateTable` and `CandidateFilters` communicate only through `useSearchParams` — no shared client state.
- Validation is local to `CandidateForm` and returns `{ valid: boolean; errors: Record<string,string> }`, mirroring the validation shape already established in `packages/shared/`.

**State:** local `useState` + `useEffect`. The URL holds anything that needs to survive a refresh.

---

## Functional Checklist

The following must all work end-to-end before the build is considered done:

- [ ] List renders with all candidates from `GET /records`
- [ ] Status filter, stage filter, and name/email search work without page reloads
- [ ] Filters and search are reflected in the URL and survive refresh + back/forward
- [ ] Clicking a row navigates to the candidate detail
- [ ] Detail page shows all fields with human-readable labels
- [ ] Status and stage can be changed from the detail page via `PATCH`
- [ ] Edit form updates the candidate via `PATCH`
- [ ] Registration form at `/candidates/new` creates via `POST` and redirects to the new detail page
- [ ] Notes can be added and deleted; deletion requires confirmation
- [ ] Missing candidate ID renders a friendly not-found view
- [ ] Every async action shows loading, success, and error feedback
- [ ] Keyboard navigation works on table rows and all controls; focus is visible
- [ ] No raw API values (e.g. `in_progress`, `personal_interview`) appear in the rendered UI

---

## Out of Scope

- Authentication (the mock API is open)
- Pagination or virtualization (candidate counts are small)
- Internationalization (Ana's team works in English)
- Automated tests (manual verification per the checklist above is sufficient)
- Adding candidate types to `packages/shared/` (the API owns the shape; duplicating it adds a sync burden with no second consumer)

---

## Final Goal

A focused internal tool that Ana's team can open tomorrow morning and use to run the Executive Assistant pipeline without losing notes or stepping on each other's edits — visually consistent with the rest of TrackFlow, operationally dense, and reliably honest about loading and error states.
