# TrackFlow

An AI-powered platform for last-mile delivery and warehouse management.

TrackFlow is a logistics operator running warehouses in Los Angeles and Zaragoza, serving e-commerce brands across the United States and Spain. This repository is the engineering platform that powers the company — a growing monorepo of websites, APIs, AI agents, and data pipelines built to replace manual operations with reliable, automated systems.

---

## 🚧 Currently Building

**Engagement 2 — TypeScript utilities for inventory and carrier scoring**

See `docs/briefs/` for the active brief.

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

### 🟡 Engagement 2 — Inventory & Carrier Scoring Engine *(brief documented, code not yet started)*

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
| 2 | Inventory & carrier scoring (TypeScript) | 🟡 In progress |
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
trackflow-logistics-ai-platform/
├── apps/                          # User-facing products
│   └── marketing-site/            # Engagement 1 — corporate site
│       ├── assets/
│       │   ├── css/               # Compiled Tailwind output (styles.css)
│       │   ├── js/                # Client-side scripts (validation.js)
│       │   └── images/            # Static images
│       └── *.html                 # index, application, privacy
│
├── packages/                      # Shared code libraries
│   ├── shared/                    # Types + utilities
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
├── workflows/                     # n8n automation workflows
│
├── docs/                          # Documentation
│   ├── briefs/                    # Stakeholder briefs
│
├── scripts/                       # Repo-wide utilities
└── resources/                     # Non-code shared resources
```


### Architectural Principles

- `apps/` depends on `packages/`, never the reverse
- Types are first-class and shared across the system
- Every working directory includes a README

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

This is a long-running portfolio project built during the AI Engineering program at 4Geeks Academy. [![4Geeks Academy](https://img.shields.io/badge/AI%20Engineering-4Geeks%20Academy-orange)](https://4geeksacademy.com/)

## Acknowledgment

This project uses the base architecture template from 4Geeks Academy:

- https://github.com/4GeeksAcademy/ai-engineering-company-project-monorepo

The template provides an initial monorepo structure and development framework. This repository significantly extends that foundation with custom architecture decisions, business logic, and AI system design tailored to the TrackFlow platform.

Instead of isolated demos, this project builds a **single, cohesive platform** for a realistic logistics company.

Each engagement:
- Solves a real operational problem
- Targets a specific stakeholder
- Integrates into a growing system

**Goal:** Demonstrate the ability to build real-world, scalable AI systems — not just tutorial projects.

---

## 👋 About Me

**Cory McDaniel**  
AI Engineer — Dallas-Fort Worth, TX  

Former controls engineer. Now building AI systems that help small businesses save time through automation.

- [![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/corymcdanielai/) 
- 📧 corymcdaniel01@gmail.com  
- 📍 Dallas-Fort Worth, TX  

---

## 🎯 Availability Options

###  Flexible

Currently open to opportunities in AI engineering, automation, and applied AI. Open to remote, contract, or sub-contract.