# TrackFlow

An AI-powered platform for last-mile delivery and warehouse management.

🌐 **Live demo:** [trackflow-ai-powered-logistics-plat.vercel.app](https://trackflow-ai-powered-logistics-plat.vercel.app/)

TrackFlow is a logistics operator running warehouses in Los Angeles and Zaragoza, serving e-commerce brands across the United States and Spain. This repository is the engineering platform that powers the company — a growing monorepo of websites, APIs, AI agents, and data pipelines built to replace manual operations with reliable, automated systems.

---

## 🚧 Current Status

**Engagement 2** is complete. Planning is underway for Engagement 3.

See `docs/briefs/` for past and upcoming briefs.

---

## ❗ The Problem

TrackFlow reflects real-world logistics challenges:

- **Two warehouses, two systems**  
  Los Angeles and Zaragoza operate on separate systems with no shared inventory visibility.

- **Eight carriers, no unified data**  
  Carrier assignment is manual with no performance metrics (on-time rate, cost/kg, incidents).

- **Returns reviewed by hand**  
  18–25% of orders are returned and manually processed without consistent rules.

- **Customer support is all human**  
  80% of queries are repetitive and could be automated. No ticketing system or knowledge base.

- **No CRM**  
  Account managers rely on spreadsheets and email threads.

- **Manual reporting**  
  Weekly reports require hours of manual work every Sunday night.

---

## 🧠 What’s Been Built

### ✅ Engagement 1 — Corporate Website & B2B Lead Capture *(delivered)*

- Responsive marketing site (US + Spanish markets)
- Structured intake form for qualified leads
- Replaces vague, manual inquiry process

**Tech:**
- HTML5
- Tailwind CSS
- Vanilla JavaScript
- Schema.org structured data
- Full client-side validation

📁 Location: `apps/marketing-site/`

---

### ✅ Engagement 2 — Inventory & Carrier Scoring Engine *(delivered)*

- Inventory filtering by location and stock
- Carrier scoring (cost, speed, reliability)
- Shipping cost calculations
- Data validation before order processing

**Tech:**
- Strict TypeScript
- Pure functions (no mutations)
- Full interface modeling
- Edge case handling

📁 Location: `packages/shared/`

---

## 🗺️ Roadmap

| Engagement | Focus | Status |
|----------|------|--------|
| 1 | Corporate website + lead capture | ✅ Delivered |
| 2 | Inventory & carrier scoring (TypeScript) | ✅ Delivered |
| 3 | AI-driven UI generation | ⏳ Upcoming |
| 4 | Next.js portals (operations, loyalty, client) | ⏳ Upcoming |
| 5 | Central API | ⏳ Upcoming |
| 6 | Data pipelines & telemetry | ⏳ Upcoming |
| 7 | RAG knowledge base & semantic search | ⏳ Upcoming |
| 8 | AI agents | ⏳ Upcoming |
| 9 | Workflow automation (n8n) | ⏳ Upcoming |
| 10 | Real-time dashboards & alerts | ⏳ Upcoming |

---

## 🏗️ Repository Architecture

```text
trackflow/
├── apps/                          # User-facing products
│   └── marketing-site/            # Engagement 1 — corporate site
│       ├── assets/
│       │   ├── css/               # Compiled Tailwind output (styles.css)
│       │   ├── js/                # Client-side scripts (validation.js)
│       │   └── images/            # Static images
│       └── *.html                 # index, application, privacy
│
├── packages/                      # Shared code libraries
│   ├── shared/                    # @repo/shared-types: types + utilities
│   └── tailwind-config/           # Shared Tailwind setup
│
├── agents/                        # AI agents (Engagement 8)
│   ├── _template/                 # Starter pattern
│   └── tools/                     # Reusable agent tools
│
├── data/                          # Data engineering (Engagement 6)
│   ├── raw/                       # Source data
│   ├── process/                   # Cleaned data
│   ├── pipelines/                 # ETL logic
│   └── eval/                      # AI evaluation datasets
│
├── skills/                        # Reusable agent capabilities
│   ├── _template/                 # Starter pattern for new skills
│   ├── code-review/
│   ├── data-analysis/
│   └── research/
│
├── workflows/                     # n8n automation workflows
│
├── docs/                          # Documentation
│   ├── briefs/                    # Stakeholder briefs (per engagement)
│   ├── standards/                 # Cross-cutting standards (visibility, etc.)
│   └── archive/                   # Historical planning artifacts
│
├── scripts/                       # Repo-wide utilities
└── resources/                     # Non-code shared resources
```


### Architectural Principles

- `apps/` depends on `packages/`, never the reverse
- Types are first-class and shared across the system
- Meaningful top-level working directories include a README

---

## ⚙️ Tech Stack

| Layer | Tools |
|------|------|
| Frontend | HTML5, Tailwind CSS, JS → React + Next.js (planned) |
| Language | TypeScript |
| Backend | Node.js (planned) |
| AI | RAG, LLM agents, semantic search |
| Automation | n8n workflows |
| Infra | Monorepo, GitHub Codespaces |

---

## 📌 About This Project

A long-running portfolio project built during the AI Engineering program at 4Geeks Academy. [![4Geeks Academy](https://img.shields.io/badge/AI%20Engineering-4Geeks%20Academy-orange)](https://4geeksacademy.com/)

Rather than isolated demos, TrackFlow is a **single, cohesive platform** for a realistic logistics company. Each engagement solves a real operational problem for a specific stakeholder and integrates into the growing system.

Built on the [4Geeks monorepo template](https://github.com/4GeeksAcademy/ai-engineering-company-project-monorepo), then significantly extended with custom architecture, business logic, and AI system design.

---

## 👋 About Me

**Cory McDaniel**  
AI Engineer — Dallas-Fort Worth, TX  

Former controls engineer. Now building AI systems that help small businesses save time through automation.

- [![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/corymcdanielai/) 
- 📧 corymcdaniel01@gmail.com  
- 📍 Dallas-Fort Worth, TX  

---

## 🎯 Availability

Open to AI engineering, automation, and applied AI roles — remote, contract, or sub-contract.