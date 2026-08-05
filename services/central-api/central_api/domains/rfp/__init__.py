"""RFP agentic-workflow domain (Engagement 9).

A multi-agent LangGraph workflow that turns an uploaded RFP PDF into a per-department pricing
proposal: intake and routing, per-department generation and evaluation, human approval, and final
document synthesis. This package owns the durable ticket schema and the HTTP boundary; the graph and
its nodes are added in later phases. It reuses the Engagement 8 agent runtime, guardrails, and trace
store, and the Engagement 7 RAG retrieval/generation functions.
"""
