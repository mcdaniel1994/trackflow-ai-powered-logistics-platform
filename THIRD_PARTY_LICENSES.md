# Third-Party Licenses

TrackFlow's own code is proprietary (see [LICENSE](LICENSE)). This project depends
on open-source software distributed under a variety of licenses. The vast
majority (~650 of ~660 unique third-party packages across the Python and
JavaScript dependency trees) are under permissive terms — MIT, BSD, Apache-2.0,
or ISC — and are not enumerated individually here; the full tree can be
regenerated at any time with `pip-licenses` (per Python service/package venv)
or `npx license-checker` (npm workspace root).

This file exists to give explicit notice and attribution for the dependencies
that carry copyleft or other non-permissive terms, as surfaced by a full
dependency/license audit (2026-07-20). No AGPL or CC-BY-NC dependencies were
found anywhere in the tree.

## Engagement 6.5.a forecasting extra

The offline-only `data` project's `forecasting` extra was owner-approved for Engagement 6.5.a.
It is not installed by the production `uv sync --frozen --no-dev` path. The stricter engagement
specification requires every package added by this extra to be recorded, including permissive
packages:

| Package | Version | License | Direct / Transitive | Notes |
|---|---|---|---|---|
| [matplotlib](https://pypi.org/project/matplotlib/) | 3.11.1 | Matplotlib License (PSF-derived, permissive) | Direct | Owner-approved custom permissive license; offline chart generation |
| [numpy](https://pypi.org/project/numpy/) | 1.26.4 | BSD-3-Clause | Direct | Declared directly because forecasting code imports its array API; `<2` retains Python 3.11 strict-mypy compatibility |
| [scikit-learn](https://pypi.org/project/scikit-learn/) | 1.9.0 | BSD-3-Clause | Direct | Offline Random Forest implementation |
| [scipy](https://pypi.org/project/scipy/) | 1.17.1 | BSD-3-Clause | Direct | D'Agostino–Pearson K² implementation; its wheel dynamically links LGPL `libquadmath`, recorded below |
| [contourpy](https://pypi.org/project/contourpy/) | 1.3.3 | BSD-3-Clause | Transitive (`matplotlib`) | Contour support |
| [cycler](https://pypi.org/project/cycler/) | 0.12.1 | BSD-3-Clause | Transitive (`matplotlib`) | Plot style cycles |
| [fonttools](https://pypi.org/project/fonttools/) | 4.63.0 | MIT | Transitive (`matplotlib`) | Font processing |
| [joblib](https://pypi.org/project/joblib/) | 1.5.3 | BSD-3-Clause | Transitive (`scikit-learn`) | Estimator support |
| [kiwisolver](https://pypi.org/project/kiwisolver/) | 1.5.0 | BSD-3-Clause | Transitive (`matplotlib`) | Plot layout constraints |
| [narwhals](https://pypi.org/project/narwhals/) | 2.24.0 | MIT | Transitive (`scikit-learn`) | Dataframe compatibility layer |
| [pillow](https://pypi.org/project/pillow/) | 12.3.0 | HPND | Transitive (`matplotlib`) | PNG output |
| [threadpoolctl](https://pypi.org/project/threadpoolctl/) | 3.6.0 | BSD-3-Clause | Transitive (`scikit-learn`) | Native thread-pool control |
| [libquadmath](https://gcc.gnu.org/onlinedocs/libquadmath/) | bundled with SciPy wheel | LGPL-2.1-or-later | Transitive native library (`scipy`) | Used unmodified and dynamically linked |

## Engagement 8 LangGraph agent stack

Added to `services/central-api` for the Engagement 8 LangGraph agent (owner-approved 2026-07-30).
Every package added by this change is **permissive** (MIT / BSD / Apache-2.0), so none introduces a
new copyleft obligation; they are recorded here for provenance because they are a direct engagement
dependency.

| Package | Version | License | Direct / Transitive | Notes |
|---|---|---|---|---|
| [langgraph](https://pypi.org/project/langgraph/) | 1.2.10 | MIT | Direct | Agent graph runtime |
| [langchain-openai](https://pypi.org/project/langchain-openai/) | 1.4.1 | MIT | Direct | OpenAI chat/tool-calling binding for the agent LLM (`gpt-4o-mini`) |
| [langchain-core](https://pypi.org/project/langchain-core/) | 1.5.3 | MIT | Transitive (`langgraph`, `langchain-openai`) | Core message/runnable abstractions |
| [langgraph-checkpoint](https://pypi.org/project/langgraph-checkpoint/) | 4.1.1 | MIT | Transitive (`langgraph`) | Checkpointer interface (in-memory saver) |
| [langgraph-prebuilt](https://pypi.org/project/langgraph-prebuilt/) | 1.1.0 | MIT | Transitive (`langgraph`) | Prebuilt nodes (e.g. ToolNode) |
| [langgraph-sdk](https://pypi.org/project/langgraph-sdk/) | 0.4.2 | MIT | Transitive (`langgraph`) | SDK types |
| [langchain-protocol](https://pypi.org/project/langchain-protocol/) | 0.0.18 | MIT | Transitive | Agent/streaming protocol types |
| [langsmith](https://pypi.org/project/langsmith/) | 0.10.13 | MIT | Transitive (`langchain-core`) | Tracing client. **Disabled by design** — TrackFlow uses a self-hosted Postgres trace store; no `LANGSMITH_*`/`LANGCHAIN_TRACING*` env is set, so no prompts or traces are transmitted off-box. |
| [tiktoken](https://pypi.org/project/tiktoken/) | 0.13.0 | MIT | Transitive (`langchain-openai`) | Token counting |
| [ormsgpack](https://pypi.org/project/ormsgpack/) | 1.12.2 | Apache-2.0 OR MIT | Transitive (`langgraph-checkpoint`) | Checkpoint serialization |
| [uuid-utils](https://pypi.org/project/uuid-utils/) | 0.17.0 | BSD-3-Clause | Transitive | Fast UUIDs |
| [xxhash](https://pypi.org/project/xxhash/) | 3.8.1 | BSD-2-Clause | Transitive | Hashing |
| [zstandard](https://pypi.org/project/zstandard/) | 0.25.0 | BSD-3-Clause | Transitive | Compression |
| [requests-toolbelt](https://pypi.org/project/requests-toolbelt/) | 1.0.0 | Apache-2.0 | Transitive (`langsmith`) | HTTP multipart helper |

## Copyleft / weak-copyleft dependencies

| Package | Version | License | Ecosystem | Direct / Transitive | Notes |
|---|---|---|---|---|---|
| [psycopg2-binary](https://pypi.org/project/psycopg2-binary/) | 2.9.12 | LGPL | Python | Direct (`services/central-api`) | PostgreSQL driver; used unmodified as a dynamically-linked dependency |
| [psycopg](https://pypi.org/project/psycopg/) / psycopg-binary | 3.3.4 | LGPL-3.0-only | Python | Direct (`data`), transitive into `services/central-api` via the `trackflow-data-pipelines` path dependency | PostgreSQL driver; used unmodified |
| [text-unidecode](https://pypi.org/project/text-unidecode/) | 1.3 | Artistic License / GPL / GPLv2+ (multi-license) | Python | Transitive (`prefect` → `python-slugify` → `text-unidecode`) | Used unmodified as installed |
| [certifi](https://pypi.org/project/certifi/) | varies (2026.x) | MPL-2.0 | Python | Transitive (present in every Python service/package venv) | CA bundle; weak/file-level copyleft |
| [orjson](https://pypi.org/project/orjson/) | 3.11.9 | MPL-2.0 AND (Apache-2.0 OR MIT) | Python | Transitive | Weak/file-level copyleft on the MPL-licensed portion |
| [pathspec](https://pypi.org/project/pathspec/) | 1.1.1 | MPL-2.0 | Python | Transitive | Weak/file-level copyleft |
| [@img/sharp-libvips-darwin-arm64](https://www.npmjs.com/package/@img/sharp-libvips-darwin-arm64) | 1.2.4 | LGPL-3.0-or-later | JavaScript | Transitive (`next` → `sharp`) | Prebuilt native image-processing binary |
| [axe-core](https://www.npmjs.com/package/axe-core) | 4.11.4 | MPL-2.0 | JavaScript | Transitive (`eslint-plugin-jsx-a11y`) | Lint-time only, not shipped at runtime |
| [lightningcss](https://www.npmjs.com/package/lightningcss) / lightningcss-darwin-arm64 | 1.32.0 | MPL-2.0 | JavaScript | Transitive (`vitest` → `vite`) | Build/test-time only, not shipped at runtime |

## Informational (no action needed)

| Package | Version | License | Ecosystem | Notes |
|---|---|---|---|---|
| [caniuse-lite](https://www.npmjs.com/package/caniuse-lite) | 1.0.30001793 | CC-BY-4.0 | JavaScript | Transitive (`browserslist`/`autoprefixer`), dev/build-time only, data file rather than code |
| [aiohappyeyeballs](https://pypi.org/project/aiohappyeyeballs/) | 2.7.1 | Python Software Foundation License | Python | Permissive in practice; not one of MIT/BSD/Apache-2.0/ISC specifically |

## Attribution notices

Full license texts for the packages above are available from their respective
project pages linked in the tables, or via SPDX (https://spdx.org/licenses/).
Copyright for each listed package remains with its respective authors.
