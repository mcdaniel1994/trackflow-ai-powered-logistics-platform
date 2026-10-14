# Public support

Engagement 11's fixed `POST /public-support/query` endpoint. It accepts only a question,
English/Spanish answer language, US/Spain policy selection, and up to three recent exchanges.
Its gateway secret authenticates a service, never a staff user. No database dependency,
MCP tool, staff principal, agent graph, structured memory, or trace recorder is reachable here.

Retrieval always targets `trackflow_public`; the existing internal `RAG_COLLECTION` setting
cannot override it. Input, history, retrieved evidence and output pass deterministic checks;
current evidence alone supplies facts. Answers and safe outcomes are the only public response
content. Failure logs contain allowlisted outcome/error-type metadata only.

`PUBLIC_SUPPORT_ENABLED=false` by default. Credentials and collection are mandatory. Admission
reserves capacity before provider calls: two requests active, 30/min globally, 200 per UTC day.
The bounded counters are process-local and reset on restart. Keep one API worker and one replica;
multiple instances require a shared limiter before public enablement. A timed-out request keeps
its slot until bounded upstream I/O actually finishes. Backend deadline is 30 seconds, Qdrant
and embedding I/O five seconds each, generation 15 seconds, SDK retries disabled.

Run mocked coverage with `tests/test_public_support.py`; deployment and paid indexing/verification
are separate steps in [the runbook](../../../../../docs/runbooks/customer-demo.md).
