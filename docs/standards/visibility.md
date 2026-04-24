# Visibility & Discoverability Standards

**Last reviewed:** April 2026  
**Next review due:** July 2026 (quarterly — see Section 11)

This file is the authority on how TrackFlow's public-facing pages get found — by search engines, AI engines, and human visitors.

AI coding agents must reference this file before generating any public-facing page. All generated public pages must comply with sections 1 through 6. Flag any violation before proceeding (see Section 10 for the override path).

---

## Scope

This file applies to public-facing web surfaces only — the marketing site (`apps/marketing-site/`), any future public portions of customer or partner portals, and any future public content (blog, knowledge base, documentation).

It does NOT apply to authenticated apps, internal dashboards, or anything behind a login. Those surfaces have different concerns (auth flows, runtime performance, internal usability) and are governed separately.

---

## Note on this file's dual purpose

TrackFlow is a portfolio project. These standards govern TrackFlow's public web surfaces, and they also serve as a demonstration of professional web engineering practices — engineers and recruiters viewing the source should be able to verify the standards are met by inspection.

---

## Workflow — Do This In Order

When building or auditing any public page, follow this sequence:

- Audit — check existing structure, meta tags, schema, and bot access  
- Fix structure — semantic HTML, heading hierarchy, accessibility  
- Apply SEO metadata — title, description, canonical, Open Graph, Twitter Cards  
- Apply GEO formatting — answer-first structure, statistics, citations, FAQs  
- Add schema — correct JSON-LD type for the page, validate before launch  
- Performance check — Core Web Vitals, image optimization, load speed  
- Validate — Google Rich Results Test, schema validator, indexing check  
- Instrument — confirm measurement is in place per Section 11  

Never skip steps or apply them out of order. If a step reveals a violation, fix it before moving to the next, or invoke the override process in Section 10.

---

## How AI Coding Agents Should Use This File

- Reference this file before generating or modifying any public-facing page  
- All generated public pages must comply with sections 1 through 6  
- Flag any architectural decision that would compromise these standards before proceeding  
- Propose a compliant alternative — do not silently deprioritize any standard  
- When in doubt, accessibility and semantic correctness take priority over everything else  
- If a standard appears to conflict with another standard or a project requirement, follow the resolution process in Section 10 — do not guess  
- This file does NOT apply to authenticated UI work — apply judgment but skip the SEO/GEO sections when working behind login  

---

## 1. Semantic HTML

- Use meaningful, purpose-driven tags (`<article>`, `<section>`, `<nav>`, `<main>`, `<aside>`, `<header>`, `<footer>`)  
- Maintain a logical heading hierarchy — one `<h1>` per page, followed by `<h2>` and `<h3>` in order  

> Note: HTML5 technically permits multiple `<h1>` elements within sectioning contexts, but for SEO and assistive tech consistency, use one per page  

- Never skip heading levels for visual styling purposes — use CSS instead  
- Use `<ul>` / `<ol>` for lists, `<blockquote>` for quotes, `<time>` for dates  
- Prefer native HTML elements over ARIA roles when a semantic element already exists  

Critical content must be present in the initial server-rendered or static HTML. Do not inject primary content via client-side JavaScript — most AI crawlers do not execute JS reliably, and crawl budget for JS rendering is limited even for Googlebot. For the current marketing site, this means fully static HTML files. For future Next.js portals, prefer SSG or SSR over CSR for any public-facing route.

---

## 2. Web Accessibility (WCAG 2.1 AA)

- All images must have descriptive alt text; decorative images use `alt=""`  
- All interactive elements must be keyboard navigable and have visible focus states  
- Color contrast ratio must meet AA minimum: 4.5:1 for body text, 3:1 for large text  
- ARIA labels required on icon-only buttons, form inputs without visible labels, and landmark regions  
- Forms must have associated `<label>` elements — never rely on placeholder text alone  
- No content should rely solely on color to convey meaning  

Baseline screen reader for testing: NVDA on Windows + Firefox. Spot-check with VoiceOver on macOS/iOS for any page intended to convert mobile users (lead capture forms, contact forms, anything with a CTA)

---

## 3. SEO (Traditional Search)

### Title tags

Every page requires a unique, descriptive `<title>` tag containing the primary keyword  
Front-load the primary keyword in the first 50 characters — Google truncates titles based on pixel width (~600px), not character count, and rewrites titles roughly 60% of the time  
Write for humans first; the character count is a guideline, not a hard rule. Aim for clarity over cramming  

### Meta descriptions

Every page requires a unique `<meta name="description">`  
Target roughly 140–160 characters as a guideline. Google rewrites descriptions roughly 70% of the time, so prioritize a compelling first sentence over hitting an exact length  
Write the first 120 characters as if they will be the entire snippet, because often they will  

### Required tags on every page

- Canonical URL: `<link rel="canonical">`  
- Open Graph: `og:title`, `og:description`, `og:image (1200×630px)`, `og:url`, `og:type`  
- Twitter Card: `twitter:card`, `twitter:title`, `twitter:description`, `twitter:image`  

### Crawlability and structure

- All pages must be crawlable — no accidental `noindex` tags in production  
- Generate and maintain `sitemap.xml` and `robots.txt`  
- Internal linking: every page should link to at least two other relevant pages  
- External links use `rel="noopener"` for security; add `noreferrer` only when intentionally stripping referrer data  
- Image filenames: lowercase, hyphens not underscores, descriptive  
- H1 must contain the primary keyword for that page  
- Page load speed under 3 seconds on a standard mobile connection (see Section 7)  

### Bilingual SEO (hreflang) — currently deferred

TrackFlow operates in the United States and Spain and will eventually serve content in both English and Spanish. The current marketing site is English-only, so hreflang tags are intentionally omitted at this stage.

When Spanish content launches:

- Every page that has a translation must declare `hreflang="en"` and `hreflang="es"`  
- Include a self-referential hreflang tag  
- Use `hreflang="x-default"` for fallback  

Do not deploy a Spanish version without hreflang.

---

## 4. GEO (Generative Engine Optimization)

Key insight: AI search engines don't rank pages — they cite sources. Being cited is the new ranking #1.

### Princeton GEO methods (Aggarwal et al., 2023)

**Methods that improved citation rates:**

| Method | Typical Impact | How to Apply |
|------|--------------|-------------|
| Cite sources | High | Add authoritative citations |
| Statistics | High | Include specific numbers |
| Quotations | Strong | Add expert quotes |
| Authoritative tone | Strong | Use confident language |
| Fluency | Strong | Improve readability |
| Easy to understand | Moderate | Simplify concepts |
| Technical terms | Moderate | Include domain terminology |
| Unique words | Moderate | Increase vocabulary diversity |

**Methods that did NOT help:**

- Keyword stuffing  
- Generic AI-generated filler content  

Strong combinations: Fluency + Statistics, Cite-sources + Quotations.

---

### Content structure rules

- Lead with the answer — answer-first always  
- Use clear question-and-answer formatting  
- Define key terms explicitly  
- Write to be cited, not just read  
- Include statistics with sourcing  
- Establish clear organizational identity  
- Define the entity clearly (TrackFlow description must remain consistent)  
- Avoid vague language  
- Use short paragraphs (2–3 sentences)  
- Use lists and tables  
- Host key content as PDFs where appropriate — Perplexity indexes PDFs directly and cites them at higher rates  

---

## 5. E-E-A-T

- Maintain a real About page  
- Display real operational signals  
- Link authoritative sources  
- Keep identity consistent  
- Maintain trust signals  
- Include roles/tenure in named content  
- Do not exaggerate scope  

### Content freshness mechanism

- Include `datePublished` and `dateModified`  
- Show "Last updated"  
- Quarterly audit  
- Flag content older than 12 months  

---

## 6. Schema.org JSON-LD

Apply appropriate schema per page type.

### Required properties

- headline, datePublished, dateModified  
- author, publisher  
- image (1200×630px)  

### Organization schema

- name, url, logo  
- foundingDate, foundingLocation  
- sameAs  
- numberOfEmployees  
- address  
- areaServed  

### Validation

- Google Rich Results Test  
- Schema.org validator  
- Do not ship failing schema  

---

## 7. Core Web Vitals & Performance

| Metric | Target |
|------|--------|
| LCP | < 2.5s |
| CLS | < 0.1 |
| INP | < 200ms |

### Implementation rules

- Lazy load images  
- Set width/height  
- Prefer static/SSR  
- Minimize JS  
- Use WebP/AVIF  
- Optimize fonts  

---

## 8. AI Bot Access

Allow all major bots in `robots.txt`, including:

- Googlebot  
- Bingbot  
- PerplexityBot  
- ChatGPT-User  
- GPTBot  
- ClaudeBot / Claude-Web / Claude-SearchBot  
- anthropic-ai  
- Applebot  

### llms.txt

Optional but recommended emerging standard.

---

## 9. Geographic Targeting (US + Spain)

The current site is US-primary and English-only. Spain expansion is planned but deferred — do not build Spanish pages until `hreflang` implementation is ready (see Section 3).

- Reference real service geography naturally in page copy  
- Maintain Google Business Profiles for both warehouse locations  
- Build local citations over time  
- When Spanish pages launch, follow the hreflang requirements in Section 3 fully — no auto-translate shortcuts  

---

## 10. Overrides and Conflict Resolution

### Priority order

1. Accessibility  
2. Semantic correctness  
3. Performance  
4. SEO / GEO  
5. Schema  
6. Geographic targeting  

### Override process

- Document the conflict and the constraint causing it  
- Propose a compliant alternative  
- Log the deviation in a code comment or PR description  
- Re-evaluate at the next quarterly review  

---

## 11. Measurement & Review Cadence

### Monthly
- Organic traffic  
- Queries & CTR  
- Indexing  
- Core Web Vitals  

### Quarterly
- AI citation tracking  
- Traffic split  
- Backlinks  
- Schema validation  
- Bot verification  
- Re-check performance standards  
- Update platform assumptions  
- Review any logged overrides  

### Annually
- Full audit  
- Competitive analysis  
- Update GEO research alignment  
- Check WCAG updates  
- Align with real performance data  

### Triggered review
- Major platform changes  
- Traffic/citation drops  
- Structural issues  
- New public surfaces
