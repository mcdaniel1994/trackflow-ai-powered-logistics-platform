# TrackFlow Courier Service Public Website — Implementation Plan

## Context

TrackFlow is a last-mile delivery and warehouse management company (founded 2009, LA + Zaragoza) undergoing digital transformation. This milestone (Milestone 1: Web) delivers a production-ready public website: a branded landing page and a B2B information request form.

Source requirements come from four documents:
- `CONTEXT.md` — TrackFlow brand/content specifics, exact copy text, form fields, error messages, success message, Schema.org markup
- `planning_prompt.docx` — Technical implementation spec (file structure, HTML/CSS/JS requirements, accessibility rules)
- `web_fundamentals.md` — Planning constraints: Semantic HTML, WCAG 2.1 AA, SEO, GEO, E-E-A-T, Schema.org, code quality
- `seo_geo.md` — Answer-first GEO structure, crawlability, page speed < 3s, E-E-A-T in content decisions

---

## Deliverables

Files located in `apps/track_flow_website/`:

```
apps/track_flow_website/
├── index.html        ← Landing page
├── application.html  ← B2B info request form
└── validation.js     ← Real-time form validation (language-aware)
```

No frameworks, no build tools. Tailwind CSS via CDN only.

---

## Tech Stack

- **HTML5** — semantic tags throughout, zero unnecessary `<div>` wrappers
- **Tailwind CSS** — via CDN, mobile-first (sm: md: lg: breakpoints), no inline styles
- **Vanilla JavaScript** — form validation + language toggle + mobile nav scroll spy
- **No frameworks, no bundlers**

---

## Implemented Features

### Core: Landing Page (`index.html`)

| Section | Content |
|---|---|
| `<header>` | TrackFlow logo + desktop nav (Home, Services, Coverage, Contact) + EN/ES toggle |
| Hero | "Logistics that scales with your e-commerce" + subheading + CTA → application.html |
| Services | 3-column grid: Warehouse Management, Last-Mile Deliveries, Reverse Logistics |
| Coverage | 2-column: US (Los Angeles) + Spain (Zaragoza) with carriers |
| Benefits | 4-item grid: Binational operation, 130+ professionals, Own technology, E-commerce specialization |
| Contact | Email + LA phone + Zaragoza phone + CTA |
| `<footer>` | Copyright + LinkedIn |
| Mobile bottom nav | Fixed 4-tab bar (Home, Services, Coverage, Contact) — visible on mobile only |

**SEO/Meta:**
- `<title>`, `<meta name="description">`, canonical URL on every page
- Open Graph tags on every page
- Schema.org JSON-LD (`Organization` type) on `index.html` — exact structure from `CONTEXT.md`
- Heading hierarchy: one `<h1>` → `<h2>` → `<h3>`

**GEO & E-E-A-T:**
- Answer-first hero with concrete stats (15 years, 130 employees, US+Spain)
- Named carriers (UPS, FedEx, DHL / MRW, SEUR, DHL), city names, founding date visible
- Schema.org with two `PostalAddress` entries and `ContactPoint`

---

### Core: Application Form (`application.html`)

**Fieldset 1 — Company Information:**

| Field | Type | Validation |
|---|---|---|
| Company name | text | Required, min 2 chars, no numbers |
| Contact person | text | Required, first + last name |
| Corporate email | email | Required, valid format |
| Phone | tel | Required, `+[code] [number]` format |
| Company website | url | Optional, valid URL |

**Fieldset 2 — Service Information:**

| Field | Type | Validation |
|---|---|---|
| Main operating country | select | Required (US / Spain / Both / Other) |
| Product type | select | Required (Fashion / Electronics / Cosmetics / Food / Other) |
| Monthly shipping volume | select | Required (0-100 / 101-500 / 501-2000 / 2000+ / Not sure) |
| Services of interest | checkbox group | Required — at least one (Warehousing / Last mile / Reverse logistics) |
| Currently work with 3PL | radio group | Required (Yes / No / Evaluating) |
| Comments | textarea | Optional, max 500 chars with live counter |
| Privacy policy | checkbox | Required, must be checked |

**Buttons:** Submit + Clear Form

**Special:** Low-volume amber warning when "0–100 shipments/month" is selected.

---

### Core: Form Validation (`validation.js`)

- Blur + submit triggers on every field
- Red border + error text on failure; green border on success
- `aria-invalid` toggled dynamically; error `<span>` wired via `aria-describedby`
- Exact error messages from `CONTEXT.md` (language-aware — switches with EN/ES toggle)
- Success banner on valid submit with exact copy from `CONTEXT.md`
- Focus moves to first invalid field on failed submit
- Clear form resets all visual states

---

### UI/UX & Accessibility Improvements

#### 1. Skip to Content Link
- Visually hidden (`sr-only`) link as the **first focusable element** in both pages
- Becomes visible on Tab focus → jumps to `#main-content`
- Appears before the TrackFlow logo in tab order

#### 2. Language Toggle (EN / ES)
- Button in the header on both pages
- All visible text uses `data-i18n="key"` attributes; placeholders use `data-i18n-placeholder`
- Inline `TRANSLATIONS` object with complete EN and ES string sets
- `window.currentLang` + `localStorage('tf-lang')` — persists across pages
- `validation.js` reads `window.TRANSLATIONS[currentLang].errors.*` at validation time so error messages also switch language

#### 3. Mobile Bottom Navigation
- Hamburger button and dropdown removed from both pages
- Fixed bottom bar (`md:hidden`) with icon + label for each section
- `index.html`: Home, Services, Coverage, Contact — active tab highlighted via `IntersectionObserver` scroll spy
- `application.html`: Home, Services, Coverage, Apply — Apply tab has `aria-current="page"`
- `body` has `pb-16 md:pb-0` so content is never hidden behind the bar

#### 4. Tab Navigation — Focusable Section Cards
All 9 `<article>` cards have `tabindex="0"` + `focus:ring-2 focus:ring-blue-500 focus:ring-offset-2`:
- 3 service cards (Services section)
- 2 coverage cards (Coverage section)
- 4 benefit cards (Why TrackFlow section)

#### 5. Keyboard-Accessible Components
- All nav links, buttons, CTAs, and footer links have explicit `focus:ring` states
- Bottom nav links have `focus:bg-blue-50` on focus
- No interactive element is reachable only by mouse

---

## Responsive Breakpoints

| Viewport | Layout |
|---|---|
| 375px (mobile) | Single column, stacked sections; bottom nav visible |
| 768px (tablet) | 2-column grids; bottom nav hidden, desktop nav shown |
| 1280px (desktop) | Full 3–4 column layouts |

---

## Source Document Cross-Reference

| Requirement | Source |
|---|---|
| File structure, no framework | `Courier Service Public Website.docx` |
| TrackFlow copy, form fields, error/success messages | `CONTEXT.md` |
| Semantic HTML, zero unnecessary divs | `Courier Service Public Website.docx` + `web_fundamentals.md` |
| WCAG 2.1 AA accessibility | `web_fundamentals.md` + `seo_geo.md` |
| GEO answer-first, E-E-A-T signals | `web_fundamentals.md` + `seo_geo.md` |
| Schema.org JSON-LD (exact structure) | `CONTEXT.md` |
| Open Graph, meta tags | `Courier Service Public Website.docx` |
| Page speed < 3s | `seo_geo.md` |
| Low-volume business warning | `CONTEXT.md` |
| Exact success/error message copy | `CONTEXT.md` |
| Language toggle (EN/ES) | UI/UX improvement |
| Mobile bottom navigation | UI/UX improvement |
| Skip to content link | Accessibility improvement |
| Focusable article cards | Accessibility improvement |

---

## Verification Checklist

**Core functionality:**
1. Open `index.html` — all 6 sections render, nav links scroll to correct sections, CTA opens application.html
2. Resize to 375px, 768px, 1280px — no overflow, readable text, proper stacking
3. Submit empty form — all required field errors appear with exact messages from CONTEXT.md
4. Fill invalid email/phone — field-specific error messages appear
5. Fill all fields correctly, check privacy box, submit — exact success message appears
6. Click "Clear Form" — all fields and visual states reset
7. Select "0–100" volume — amber low-volume warning appears

**Accessibility:**
8. Tab through `index.html` — first Tab shows "Skip to content"; Enter jumps to `#main-content`
9. Continue Tab — reaches all service, coverage, and benefit article cards
10. All interactive elements show visible focus ring

**Language toggle:**
11. Click EN/ES toggle on `index.html` — all text switches; reload — language persists
12. Click toggle on `application.html` — labels, legends, select options, button text all switch
13. Trigger a validation error in Spanish — error message displays in Spanish

**Mobile navigation:**
14. Resize to 375px — fixed bottom nav bar appears; no hamburger in header
15. Scroll through `index.html` — active section tab highlights automatically
16. On `application.html` — "Apply" tab is highlighted

**Quality:**
17. Run Lighthouse — target 90+ Accessibility and SEO scores
18. Validate JSON-LD with Google's Rich Results Test
19. Zero console errors on both pages
