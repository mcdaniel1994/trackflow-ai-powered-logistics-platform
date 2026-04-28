# `apps/marketing-site/`

Public-facing TrackFlow marketing website and B2B lead capture flow.

## Status

Delivered in Engagement 1.

**Live URL:** https://trackflow-ai-powered-logistics-plat.vercel.app/ (deployed via Vercel)

## Purpose

- Present TrackFlow services for United States and Spain markets
- Capture qualified logistics leads through the application form
- Provide public trust and compliance pages (privacy, crawlability, sitemap)

## Key Files

- `index.html` - Landing page
- `application.html` - Lead capture form
- `privacy.html` - Privacy policy
- `llms.txt` - AI crawler guidance
- `robots.txt` - Bot crawling policy
- `sitemap.xml` - Search discovery map
- `assets/css/styles.css` - Site styles
- `assets/js/validation.js` - Client-side form validation

## Working Rules

Before modifying public-facing pages, read `docs/standards/visibility.md` and follow sections 1 through 6.

## Local Preview

From this folder:

```bash
python3 -m http.server 8080
```

Then open `http://localhost:8080`.
