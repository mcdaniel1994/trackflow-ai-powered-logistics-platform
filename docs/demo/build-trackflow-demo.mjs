import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FINAL_PPTX = process.env.FINAL_PPTX ?? path.join(HERE, "TrackFlow-Final-Demo.pptx");

const C = {
  canvas: "#FFFFFF",
  ink: "#0C1421",
  muted: "#5E6878",
  panel: "#EDF1F5",
  rule: "#B8C1CC",
  accent: "#6DCBF4",
  accentStrong: "#3D8DFF",
  trackflow: "#D98B65",
  deep: "#111A27",
};

const W = 1280;
const H = 720;

async function imageBytes(name) {
  return new Uint8Array(await fs.readFile(path.join(HERE, "assets", name)));
}

function addText(slide, name, text, position, style = {}) {
  const box = slide.shapes.add({
    geometry: "textbox",
    name,
    position,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  box.text = text;
  box.text.style = {
    fontSize: 24,
    typeface: "Helvetica Neue",
    color: C.ink,
    verticalAlignment: "top",
    ...style,
  };
  return box;
}

function addRule(slide, left, top, width, color = C.rule, height = 2) {
  return slide.shapes.add({
    geometry: "rect",
    name: `rule-${left}-${top}`,
    position: { left, top, width, height },
    fill: color,
    line: { style: "solid", fill: "none", width: 0 },
  });
}

function addFooter(slide, page) {
  addText(slide, `footer-${page}`, String(page).padStart(2, "0"), { left: 1184, top: 668, width: 42, height: 22 }, {
    fontSize: 14,
    color: C.muted,
    alignment: "right",
  });
}

function addTitle(slide, title, subtitle, page) {
  addText(slide, `title-${page}`, title, { left: 64, top: 42, width: 1152, height: 66 }, {
    fontSize: 50,
    bold: true,
    color: C.ink,
  });
  if (subtitle) {
    addText(slide, `subtitle-${page}`, subtitle, { left: 64, top: 112, width: 1120, height: 42 }, {
      fontSize: 24,
      color: C.muted,
    });
  }
  addFooter(slide, page);
}

function setNotes(slide, talkTrack, sources) {
  slide.speakerNotes.textFrame.setText(`${talkTrack}\n\n[Sources]\n${sources.map((source) => `- ${source}`).join("\n")}\n[/Sources]`);
  slide.speakerNotes.setVisible(true);
}

async function main() {
  const hero = await fs.readFile(path.join(HERE, "..", "..", "uis", "website", "public", "images", "trackflow-operations-hero.png"));
  const overview = await imageBytes("overview.png");
  const askAi = await imageBytes("ask-ai.png");
  const rfpDesk = await imageBytes("rfp-desk.png");
  const agentOs = await imageBytes("agent-os.png");

  const deck = Presentation.create({ slideSize: { width: W, height: H } });

  // 1 — Cover / hook
  {
    const slide = deck.slides.add();
    slide.background.fill = C.canvas;
    slide.images.add({
      blob: new Uint8Array(hero),
      contentType: "image/png",
      alt: "TrackFlow warehouse and last-mile delivery operation",
      fit: "cover",
      position: { left: 688, top: 0, width: 592, height: 720 },
      crop: { left: 0.15, top: 0, right: 0.01, bottom: 0 },
    });
    slide.shapes.add({
      geometry: "rect",
      name: "cover-accent",
      position: { left: 664, top: 0, width: 24, height: 720 },
      fill: C.accent,
      line: { style: "solid", fill: "none", width: 0 },
    });
    addText(slide, "cover-eyebrow", "TRACKFLOW", { left: 64, top: 58, width: 260, height: 34 }, {
      fontSize: 22,
      bold: true,
      color: C.trackflow,
      characterSpacing: 2,
    });
    addText(slide, "cover-title", "AI that runs with\nthe operation.", { left: 64, top: 168, width: 548, height: 174 }, {
      fontSize: 62,
      bold: true,
      color: C.ink,
    });
    addText(slide, "cover-subtitle", "One operating system for warehouse, support, and commercial work.", { left: 64, top: 408, width: 520, height: 106 }, {
      fontSize: 30,
      color: C.muted,
    });
    addText(slide, "cover-byline", "Cory McDaniel · AI Engineering Final Project", { left: 64, top: 630, width: 520, height: 34 }, {
      fontSize: 20,
      color: C.ink,
    });
    setNotes(slide,
      "0:00–0:30 — Logistics operators usually have to choose between moving fast and staying in control. I built TrackFlow so they do not have to. I’m Cory McDaniel, and TrackFlow is an AI-powered operating system that connects warehouse activity, customer support, and commercial workflows in one production platform.",
      [
        "TrackFlow project brief — memory-bank/projectbrief.md",
        "TrackFlow website hero asset — uis/website/public/images/trackflow-operations-hero.png",
      ],
    );
  }

  // 2 — Problem
  {
    const slide = deck.slides.add();
    slide.background.fill = C.canvas;
    addTitle(slide, "The work was connected. The systems weren’t.", "Every handoff added delay, inconsistency, or manual reconciliation.", 2);
    const columns = [64, 455, 846];
    const items = [
      ["01", "Inventory stopped\nat the warehouse boundary.", "Los Angeles and Zaragoza operated in separate systems, so the shared picture arrived late."],
      ["02", "Support repeated\nanswers by hand.", "Policy lived in documents while most customer questions followed the same patterns."],
      ["03", "RFP work crossed\nteams manually.", "Commercial requests needed routing, drafting, review, and approval without one durable workflow."],
    ];
    for (let i = 0; i < items.length; i += 1) {
      const x = columns[i];
      addRule(slide, x, 286, 326, i === 1 ? C.trackflow : C.rule, 3);
      addText(slide, `problem-title-${i}`, items[i][1], { left: x, top: 318, width: 326, height: 118 }, {
        fontSize: 32,
        bold: true,
      });
      addText(slide, `problem-body-${i}`, items[i][2], { left: x, top: 462, width: 326, height: 126 }, {
        fontSize: 23,
        color: C.muted,
      });
    }
    setNotes(slide,
      "0:30–1:15 — TrackFlow is a logistics operator with warehouses in Los Angeles and Zaragoza. The operational problem was not a lack of effort; it was fragmentation. Inventory visibility stopped at each warehouse, support teams repeatedly answered policy questions, and commercial RFPs moved between departments by hand. Solving one screen would not solve that system. The opportunity was to build a shared operating layer where live data and AI could work together.",
      [
        "Operational problems and stakeholder needs — memory-bank/projectbrief.md",
        "Delivered platform summary — README.md",
      ],
    );
  }

  // 3 — Shared operating view
  {
    const slide = deck.slides.add();
    slide.background.fill = C.canvas;
    addTitle(slide, "Operational data becomes a shared view.", "A single authenticated workspace connects live warehouse activity with AI assistance.", 3);
    addText(slide, "solution-claim", "One place to see what is happening—and act on it.", { left: 64, top: 196, width: 310, height: 142 }, {
      fontSize: 34,
      bold: true,
    });
    addText(slide, "solution-body", "Live fulfilment totals refresh automatically. Business, technical, and agent workflows share the same operational context.", { left: 64, top: 372, width: 310, height: 154 }, {
      fontSize: 24,
      color: C.muted,
    });
    addRule(slide, 64, 572, 310, C.accentStrong, 4);
    addText(slide, "solution-proof", "Two warehouses. One system of record.", { left: 64, top: 590, width: 310, height: 52 }, {
      fontSize: 22,
      bold: true,
    });
    slide.images.add({
      blob: overview,
      contentType: "image/png",
      alt: "TrackFlow Backoffice overview with live fulfilment metrics and Ask AI",
      fit: "contain",
      position: { left: 414, top: 188, width: 802, height: 451 },
      geometry: "roundRect",
      borderRadius: 8,
    });
    setNotes(slide,
      "1:15–1:45 — The result is one authenticated workspace. On the overview, warehouse metrics refresh from the inventory system of record, while the same interface exposes business workflows, technical telemetry, and the AI assistant. This is the foundation: the AI is not floating beside the business. It operates inside the same context as the people using it.",
      [
        "Production Backoffice overview captured 2026-08-21 — https://backoffice.forgehub.cloud/",
        "Current architecture — memory-bank/techContext.md",
      ],
    );
  }

  // 4 — AI assistant demo
  {
    const slide = deck.slides.add();
    slide.background.fill = C.canvas;
    addTitle(slide, "Ask one question. Reach the right source.", "The agent routes between policy knowledge and live ticket status—with guardrails.", 4);
    slide.images.add({
      blob: askAi,
      contentType: "image/png",
      alt: "TrackFlow first-line CX agent showing grounded and safely refused answers",
      fit: "contain",
      position: { left: 64, top: 184, width: 790, height: 444 },
      geometry: "roundRect",
      borderRadius: 8,
    });
    addText(slide, "ai-step-1", "ROUTE", { left: 902, top: 210, width: 250, height: 30 }, { fontSize: 20, bold: true, color: C.accentStrong });
    addText(slide, "ai-body-1", "The graph selects RAG, a live tool, or both.", { left: 902, top: 246, width: 292, height: 74 }, { fontSize: 25, bold: true });
    addRule(slide, 902, 340, 292);
    addText(slide, "ai-step-2", "GROUND", { left: 902, top: 368, width: 250, height: 30 }, { fontSize: 20, bold: true, color: C.trackflow });
    addText(slide, "ai-body-2", "Answers stay inside approved policy and owner-scoped data.", { left: 902, top: 404, width: 292, height: 92 }, { fontSize: 25, bold: true });
    addRule(slide, 902, 520, 292);
    addText(slide, "ai-step-3", "REFUSE", { left: 902, top: 548, width: 250, height: 30 }, { fontSize: 20, bold: true, color: C.accentStrong });
    addText(slide, "ai-body-3", "When confidence or access fails, it stops safely.", { left: 902, top: 584, width: 292, height: 66 }, { fontSize: 25, bold: true });
    setNotes(slide,
      "1:45–2:35 — In the first demo, I ask the CX agent normal operational questions. It can answer a return-policy question from the knowledge base, route a ticket-status question to a live MCP tool, and reject a carrier question when it cannot return the answer safely. The important behavior is not just that it answers. It chooses the right source, respects the user’s scope and jurisdiction, and refuses instead of inventing.",
      [
        "Production CX agent conversation captured 2026-08-21 — https://backoffice.forgehub.cloud/",
        "Agent Engineering delivery summary — README.md, Engagement 8",
        "RAG Knowledge Base delivery summary — README.md, Engagement 7",
      ],
    );
  }

  // 5 — RFP workflow
  {
    const slide = deck.slides.add();
    slide.background.fill = C.canvas;
    addTitle(slide, "An RFP becomes an approved proposal.", "A multi-agent workflow coordinates drafting, evaluation, and human decisions.", 5);
    slide.images.add({
      blob: rfpDesk,
      contentType: "image/png",
      alt: "TrackFlow RFP Desk with an approved multi-department proposal",
      fit: "contain",
      position: { left: 64, top: 180, width: 760, height: 428 },
      geometry: "roundRect",
      borderRadius: 8,
    });
    const steps = [
      ["01", "Intake + route", "Extract the PDF, validate it, and assign the right departments."],
      ["02", "Draft + evaluate", "Generate grounded sections and score them against deterministic rules."],
      ["03", "Approve + assemble", "Pause each branch for a human, then publish the final proposal."],
    ];
    for (let i = 0; i < steps.length; i += 1) {
      const y = 188 + i * 150;
      addText(slide, `rfp-number-${i}`, steps[i][0], { left: 876, top: y, width: 52, height: 34 }, { fontSize: 20, bold: true, color: C.accentStrong });
      addText(slide, `rfp-title-${i}`, steps[i][1], { left: 940, top: y - 2, width: 280, height: 56 }, { fontSize: 24, bold: true });
      addText(slide, `rfp-body-${i}`, steps[i][2], { left: 940, top: y + 50, width: 280, height: 82 }, { fontSize: 21, color: C.muted });
      if (i < 2) addRule(slide, 876, y + 140, 334);
    }
    setNotes(slide,
      "2:35–3:30 — The second demo is the RFP Desk. A user uploads a PDF. The workflow extracts and validates it, routes work to the relevant departments, generates policy-grounded drafts, and evaluates them against rules such as currency, SLA, returns, discounts, and prohibited carrier rates. Each department then pauses independently for a human decision. Only after every branch is approved does the workflow assemble the final downloadable proposal. That keeps automation fast without removing accountability.",
      [
        "Production RFP Desk captured 2026-08-21 — https://backoffice.forgehub.cloud/agent-os/rfp",
        "Automated RFP Desk delivery summary — README.md, Engagement 9",
        "Active implementation record — memory-bank/progress.md, Engagement 9",
      ],
    );
  }

  // 6 — Engineering decisions
  {
    const slide = deck.slides.add();
    slide.background.fill = C.canvas;
    addTitle(slide, "Guarded. Grounded. Observable.", "The hardest problem was making agent behavior trustworthy under real operational constraints.", 6);
    addText(slide, "engineering-lead", "Three decisions made the system production-minded:", { left: 64, top: 192, width: 330, height: 90 }, {
      fontSize: 31,
      bold: true,
    });
    const decisions = [
      ["Grounded", "RAG and live tools replace guessing."],
      ["Bounded", "Guardrails and human interrupts stop unsafe loops."],
      ["Traceable", "Paths record latency, tokens, cost, tools, and outcomes."],
    ];
    for (let i = 0; i < decisions.length; i += 1) {
      const y = 318 + i * 104;
      addText(slide, `decision-title-${i}`, decisions[i][0], { left: 64, top: y, width: 160, height: 34 }, { fontSize: 24, bold: true, color: i === 1 ? C.trackflow : C.accentStrong });
      addText(slide, `decision-body-${i}`, decisions[i][1], { left: 208, top: y, width: 222, height: 80 }, { fontSize: 21, color: C.muted });
    }
    slide.images.add({
      blob: agentOs,
      contentType: "image/png",
      alt: "TrackFlow Agent OS with ordered node trace, tokens, costs, and guardrail outcomes",
      fit: "contain",
      position: { left: 458, top: 184, width: 758, height: 426 },
      geometry: "roundRect",
      borderRadius: 8,
    });
    setNotes(slide,
      "3:30–4:15 — The hardest engineering problem was trust. A useful answer is not enough if you cannot explain where it came from or stop it when the context is wrong. I chose explicit LangGraph workflows over an opaque agent loop, MCP boundaries over direct service access, deterministic evaluators and iteration caps over unlimited retries, and durable human interrupts for high-impact approval. Agent OS makes those decisions visible: the exact graph path, tools, latency, tokens, cost, and guardrail outcomes are all inspectable. That is the part I am most proud of.",
      [
        "Production Agent OS captured 2026-08-21 — https://backoffice.forgehub.cloud/agent-os",
        "Agent Engineering delivery summary — README.md, Engagement 8",
        "Automated RFP Desk delivery summary — README.md, Engagement 9",
        "Current architecture and security boundaries — memory-bank/techContext.md",
      ],
    );
  }

  // 7 — Closing / camera Q&A
  {
    const slide = deck.slides.add();
    slide.background.fill = C.deep;
    addText(slide, "close-eyebrow", "TRACKFLOW", { left: 64, top: 62, width: 260, height: 34 }, {
      fontSize: 22,
      bold: true,
      color: C.trackflow,
      characterSpacing: 2,
    });
    addText(slide, "close-title", "Built for real operations.", { left: 64, top: 192, width: 1080, height: 96 }, {
      fontSize: 72,
      bold: true,
      color: C.canvas,
    });
    addText(slide, "close-subtitle", "Engineered for safe AI.", { left: 64, top: 308, width: 920, height: 80 }, {
      fontSize: 54,
      color: C.accent,
    });
    addRule(slide, 64, 478, 1120, "#334155", 2);
    addText(slide, "close-proof", "Operational  ·  Grounded  ·  Observable", { left: 64, top: 516, width: 780, height: 52 }, {
      fontSize: 28,
      color: C.canvas,
    });
    addText(slide, "close-name", "Cory McDaniel", { left: 64, top: 628, width: 360, height: 34 }, {
      fontSize: 20,
      color: "#CBD5E1",
    });
    setNotes(slide,
      "4:15–5:00 — Stop screen sharing or place this slide behind you, look directly into the lens, and answer the three required 4Geeks questions. Pause for two full seconds before and after each answer. Use the complete-sentence answer stems in docs/demo/TrackFlow-Demo-Script.md; replace every bracketed personal detail before recording.",
      [
        "Final project video requirements — docs/planning/demo_presentation.md",
        "TrackFlow completion summary — README.md",
      ],
    );
  }

  await fs.mkdir(path.dirname(FINAL_PPTX), { recursive: true });
  const pptx = await PresentationFile.exportPptx(deck);
  await pptx.save(FINAL_PPTX);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
