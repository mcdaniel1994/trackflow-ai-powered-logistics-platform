# TrackFlow — Company Briefing Notes

---

## 1) Why I Picked TrackFlow

I chose TrackFlow because it provides the opportunity to work with a large and varied dataset across
real business operations. I wanted experience working closer to the backend, and logistics is an
ideal domain for that. Shipping and fulfillment services are also becoming increasingly important
as the world grows more connected and online shopping becomes the norm. Beyond that, TrackFlow
operates across two countries and two warehouses, which introduces the added challenge of thinking
through scale — something I find genuinely interesting from a systems design perspective.

---

## 2) Most Interesting Departments

**Warehouse Operations**
TrackFlow's warehouse department has two significant pain points. First, its two warehouse locations
(Los Angeles and Zaragoza) run on completely separate systems with no shared inventory visibility.
Second, orders arrive manually via email in inconsistent formats and are transcribed by hand — a
slow, error-prone process that is an obvious candidate for automation.

**Customer Experience**
The customer support department is a clear automation opportunity. Roughly 80% of incoming queries
are repetitive questions that could be resolved by an AI agent — yet every single one is currently
answered by a human. There is no knowledge base, no ticketing system, and zero coverage outside
office hours. This maps directly to a RAG chatbot use case.

---

## 3) TrackFlow Automation Checklist

### 🏆 Highest Impact
- [ ] AI bot for customer tracking queries ("Where is my package?")
- [ ] AI bot for return status queries
- [ ] After-hours customer support coverage (AI never sleeps)
- [ ] Multilingual support — English + Spanish
- [ ] Automated weekly executive report (delivered 7am Monday)
- [ ] Automated returns approval engine (per-client rules)
- [ ] Automated return label generation + carrier pickup scheduling
- [ ] Order ingestion pipeline (AI parses incoming order emails)

### 🚚 Warehouse Operations
- [ ] Low stock alerts → notify brand + procurement automatically
- [ ] Inventory discrepancy detection + flagging
- [ ] Digital picking list generation (replace printed paper lists)
- [ ] Unified real-time inventory API (LA + Zaragoza warehouses)

### 📦 Carrier Management
- [ ] Carrier selection engine (destination + weight + urgency + cost)
- [ ] Unified tracking endpoint (aggregate all 8 carriers into one)
- [ ] Public tracking portal for end consumers
- [ ] Carrier performance dashboard (on-time rate, incidents, cost/kg)

### 🔄 Returns
- [ ] Automatic returns approval (configurable rules per client)
- [ ] AI product condition classifier (photo → good / damaged / dispose)
- [ ] Automated collection flow (approval → label → carrier schedule)
- [ ] Returns pattern dashboard (what's coming back, why, from who)

### 📞 Customer Experience
- [ ] First-line AI agent (tracking + return status queries)
- [ ] Semantic knowledge base (indexed for RAG)
- [ ] Unified ticketing system (email + WhatsApp + phone)
- [ ] Real-time CX dashboard
- [ ] Sentiment detection (flag frustrated customers before escalation)

### 🤝 Commercial / Sales
- [ ] CRM integration with unified client profiles
- [ ] Automated monthly client PDF report generation
- [ ] Client health dashboard with renewal risk scores
- [ ] 90-day renewal alert automation
- [ ] 30-day renewal alert automation
- [ ] Commercial agent (suggests services to prospects)

### 💻 Technology / Infrastructure
- [ ] Centralized telemetry + logging (both countries)
- [ ] Real-time monitoring with automatic alerts (replace WhatsApp method)
- [ ] Automated backups
- [ ] Automated health checks
- [ ] Incident notification system
- [ ] Technical documentation agent (reads codebase, writes docs)

### 📊 Executive Dashboard
- [ ] Global real-time KPI dashboard (shipments, delivery, costs, returns, CSAT)
- [ ] Country comparison view (USA vs Spain)
- [ ] Threshold alerts for key metrics
- [ ] Natural language AI assistant for business questions
- [ ] Auto-generated weekly report (Monday 7am delivery)

---

### 🎯 My AI Engineering Sweet Spot (RAG + LLM Track)
- [ ] Customer query RAG chatbot
- [ ] Semantic search over logistics knowledge base
- [ ] LLM + data pipeline for executive report
- [ ] LLM agent for client PDF report generation
- [ ] Returns pattern analysis (LLM summarizing structured data)