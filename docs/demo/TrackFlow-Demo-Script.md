# TrackFlow Final Demo Script

Target length: 5:00. Audience: 4Geeks reviewers, hiring managers, and portfolio viewers who understand business but may not be engineers.

This version is designed for Descript. Record each section as a separate scene so timing, browser crops, camera placement, and transitions can be adjusted independently.

## 0:00–0:25 — Hook and introduction

**Descript scene:** Open with 8–10 seconds of realistic warehouse B-roll under the hook, then cut to a chest-up camera shot for your name and project introduction. Add one minimal lower third: **Cory McDaniel — Creator, TrackFlow**.

“Logistics operators  have to focus on moving fast and staying in control. I built TrackFlow to help with both. I’m Cory McDaniel, and TrackFlow is an AI-powered operating system that connects warehouse activity, customer support, commercial workflows, and management reporting across the United States and Spain. To understand why I built it this way, it helps to start with the operational problem.”

## 0:25–1:00 — Problem and opportunity

**Descript scene:** Use warm, realistic operational B-roll for the fragmentation examples, cutting every 4–6 seconds. Optional understated labels: **Fragmented Inventory**, **Repetitive Support**, **Manual RFPs**, and **Delayed Reporting**. Return to camera for the final pivot into the solution.

“TrackFlow operates warehouses in Los Angeles and Zaragoza. The operational problem was not a lack of effort; it was fragmentation. Inventory visibility stopped at each warehouse, support teams repeatedly answered the same policy questions, and commercial RFPs moved between departments by hand. Management also had to wait until Monday for manually assembled business reports.

That fragmentation created the opportunity to build one shared operating layer where live data, business workflows, and AI could work together across both locations. Before going behind the scenes, it helps to see how TrackFlow presents itself to customers.”

## 1:00–1:25 — Public website overview

**Descript scene:** Introduce the section with a brief **Public Website** title overlay, then use a full-screen browser recording. A small camera PiP can appear for the opening and closing sentence, but let the website fill the screen while scrolling.

**Screen path:**

1. Start on the hero: “Logistics that scales with your e-commerce.”
2. Briefly show the three services: Warehouse Management, Last-Mile Deliveries, and Reverse Logistics.
3. Show the United States and Spain coverage section.
4. Return to the header and move toward **Login**.

Say:

“This is TrackFlow’s public-facing website. It explains the three core services—warehouse management, last-mile delivery, and reverse logistics—along with coverage in the United States and Spain. A potential customer can understand the business and request information here. That is the customer-facing side of TrackFlow. Now let’s move behind the scenes into the operating system employees actually use.”

## 1:25–1:40 — Login and operational transition

**Descript scene:** Continue the same browser clip. Click **Login**, choose the **Admin Demo** account, and sign in. Center the crop on the login form, remove loading time in the edit, and fade in a small bottom-right camera PiP as the Overview appears.

Say:

“This login separates the public marketing experience from the authenticated operating system. I’ll use the admin demo account. Once inside, the platform brings warehouse data, business workflows, and AI into the same environment. The first example is customer support.”

Once the Overview loads, pause for one second on the live warehouse metrics before opening the CX agent.

## 1:40–2:20 — Demo 1: CX agent

**Descript scene:** Backoffice Overview → Resume recent conversation. Keep a bottom-right camera PiP while narrating, but crop tightly enough that the chat remains readable. Add small labels synchronized to the three behaviors: **Policy Answer**, **Live Tool Routing**, and **Safe Refusal**. Use the saved conversation so the recording does not depend on a new provider response.

Show these three examples:

1. “What’s the standard return window?” — point out the grounded policy answer.
2. “What is the status of ticket 1?” — explain that the agent routed to a live MCP tool.
3. “Which carrier best covers rural Aragón?” — point out the safe refusal.

Say:

“The CX agent can answer from policy knowledge, route a ticket question to a live operational tool, and stop when it cannot return an answer safely. The important behavior is not just that it answers. It chooses the right source, respects the user’s scope and jurisdiction, and refuses instead of inventing. Customer support shows how AI can assist with individual requests, but TrackFlow also uses AI for much larger, multi-step business processes.”

## 2:20–3:10 — Demo 2: Automated RFP Desk

**Descript scene:** Introduce the section with a brief **RFP Desk** title overlay, then go full-screen on the completed Northstar Home Products ticket. Use step labels—**Upload**, **Route**, **Draft**, **Evaluate**, **Approve**, **Assemble**—only as each stage is mentioned. Keep the camera off-screen until the final accountability sentence.

Show:

1. The completed ticket and extracted country, currency, volume, and deadline.
2. The routed Last-Mile and Reverse Logistics departments.
3. The approved sections and final proposal download.

Say:

“In the RFP Desk, a user uploads a PDF, and the system extracts and validates it, routes work to the correct departments, generates policy-grounded drafts, and evaluates them against deterministic business rules.

Each department then pauses independently for a human decision. Only after every branch is approved does the workflow assemble the final downloadable proposal. That makes the process faster without removing accountability. But automating a workflow like this raises an important question: how do you know the AI is actually behaving correctly?”

## 3:10–3:55 — Engineering decisions and hardest challenge

**Descript scene:** Begin full camera for the trust problem and engineering choices, with the four terms appearing one at a time: **LangGraph workflows**, **MCP boundaries**, **Deterministic evaluators**, and **Human interrupts**. Then cut to Agent OS for one successful run and one rejected run. Zoom into the ordered node trace and guardrail result; return your camera as a small PiP for the final reflection transition.

Say:

“The hardest engineering problem was trust. A useful answer is not enough if I cannot explain where it came from or stop it when the context is wrong.

I chose explicit LangGraph workflows over opaque agent loops, MCP boundaries over direct service access, deterministic evaluators with iteration caps, and durable human interrupts for high-impact approvals.

Agent OS makes those decisions visible: the graph path, tools, latency, tokens, cost, and guardrail outcomes are inspectable. TrackFlow represents a lot of what I learned during the program, so I want to finish with three quick reflections on my experience with 4Geeks.”

## 3:55–5:00 — Required 4Geeks Q&A

**Descript scene:** Introduce the section with a subtle **Reflections on 4Geeks** title, then use three separate full-camera clips with a slightly closer, warmer crop. Look directly into the lens. Leave two seconds of silence before and after each answer so every response can be edited independently. Hold on camera through the final line, then fade to a simple end card: **TrackFlow — Built by Cory McDaniel**.

1. “What made me decide to pursue AI Engineering was seeing how quickly AI was changing software and business. I already had a technical background in automation and systems, and I wanted to build on that by learning modern software and AI engineering. What almost held me back was not having the traditional computer science path, but I quickly learned that AI is helping close that gap.”
2. “The moment things really clicked for me was during the TrackFlow project. By that point, I was not just completing an assignment—I was thinking about architecture, deployment, security, agent workflows, observability, and how the entire product worked together.”
3. “What I would tell someone who is on the fence about joining 4Geeks is that its practical, real-world business projects help you apply what you are learning immediately and turn separate technical concepts into something you can actually build and demonstrate.”

## Submission description

TrackFlow is an AI-powered logistics operating system that unifies live warehouse operations, grounded customer support, automated reporting, and multi-agent RFP workflows. It combines RAG, MCP tools, LangGraph workflows, human approval, real-time interfaces, and production observability so automation remains useful, safe, and accountable.

Suggested filename: `CoryMcDaniel-TrackFlow.mp4`
