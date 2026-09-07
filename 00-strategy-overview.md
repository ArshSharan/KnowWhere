# Fact Knowledge Layer
## Pre-Development Strategy

My tech stack: **Python (FastAPI) backend + a minimal React/Vite frontend**, because the core problem (PDF parsing, LLM orchestration, embeddings, reconciliation reasoning) is Python-native, and every free-tier target below has first-class Python support.

**Decisions locked as of this revision (see §3.2 for full reasoning):** storage is **Postgres + `pgvector` via Supabase**, not Neo4j — chosen deliberately given limited build time, not as a fallback. LLM provider is **OpenAI**, using **GPT-6 Sol** for reconciliation reasoning and **GPT-5.6 Luna** for bulk per-page extraction. Full rationale below.

---

## 1. Problem Breakdown & Core Objectives

### 1.1 What is actually being asked
Strip away the framing and the deliverable is a **generalizable extraction + reconciliation pipeline**, not a Delhivery app or a macroeconomy app. The grading signal is explicit: *"it should not rely on hard-coded facts, filenames, schemas, or document-specific rules"* and they will test with **PDFs you've never seen**. Every design decision has to survive that test.

Three sub-problems, in increasing order of difficulty:

1. **Extraction** — turn unstructured PDF text/tables into structured, typed facts.
2. **Grounding** — every fact must trace back to *exact* evidence (quote + location) in its source document. This is a citation problem, not a summarization problem.
3. **Reconciliation** — given two facts (possibly from different documents, different vintages, different units), decide: do they agree, disagree, or only *appear* to disagree because of scope/time/units? This is the hardest and most differentiating part — it's explicitly called out as "the interesting part."

### 1.2 Hidden technical complexities (the parts that separate strong from average submissions)

| Hidden complexity | Why it's easy to miss | What it demands |
|---|---|---|
| **Schema-less generalization** | It's tempting to write a `DelhiveryFact` model with `revenue`, `directors`, `pincode` fields. That fails the moment a new PDF (say, a hospital's annual report) is uploaded. | A **fact envelope** that is schema-*light* by design (see §2.3), with domain-specific structure captured as data, not code. |
| **Evidence grounding at exact-quote precision** | Most naive RAG pipelines summarize a chunk and lose the traceable link between a specific number and its exact sentence. | Extraction must preserve a **verbatim span + page number**, not a paraphrase. |
| **O(n²) fact comparison** | Reconciliation naively means comparing every fact to every other fact — this explodes past a few hundred facts and is the first thing that breaks the "many PDFs" and "large PDFs" brownie points. | Candidate generation via **vector similarity before** any LLM comparison call — turn O(n²) into O(n·k). |
| **"Contradiction" vs. "different scope"** | A revenue figure of ₹6,300 Cr and ₹7,225 Cr for "Delhivery" aren't necessarily wrong — one might be standalone, one consolidated; one FY23, one FY24. Naive systems will flag this as a contradiction and lose points on judgment/nuance. | The reconciliation step needs explicit reasoning about **time period, entity scope (standalone/consolidated/group), and units** before calling something a contradiction. |
| **Reproducibility with unseen PDFs** | Anything that works because you eyeballed the Delhivery prospectus and special-cased its table layout will visibly fail on the evaluator's own PDF. | Treat your **own dataset as a test set, not a spec.** Validate on a PDF outside the two starter folders before submitting. |
| **Explainability as a first-class output** | The rubric says "show... your system's reasoning." An opaque black-box classifier score is worse than a short, readable chain of reasoning attached to each relationship. | Every corroborate/contradict/reconcile edge needs a **human-readable explanation string**, not just a label. |

### 1.3 Calibration warning — read this before building anything
The brief says, almost pointedly: *"A graph database or visualization alone is not the solution,"* and *"A smaller, understandable prototype is better than a large system whose behavior is unclear."* This is Superjoin telling you how they grade. Maximal infrastructure (Neo4j + a vector DB + a job queue + a polished frontend) that obscures *why* the system called something a contradiction will score **worse** than a smaller system with crisp, inspectable reasoning traces.

The instruction to fully implement all brownie points is honored below — but sequenced correctly: **the core loop must be legible and correct first.** Section 6 phases this explicitly so effort doesn't front-load into infrastructure that doesn't move the actual grading criteria (facts, evidence, corroboration/contradiction/reconciliation, four demonstrated cases).

---

## 2. Brownie Point Integration Strategy

All four are addressed with **one underlying architectural choice**, so they aren't four bolt-on features — they fall out of doing the core design correctly.

### 2.1 Large PDFs without significant performance issues
- Never feed an entire PDF into one LLM call. Extract text **per page** (PyMuPDF/`pdfplumber`), batch pages (e.g., 5–10 pages per call) to stay well under context limits and keep latency predictable regardless of document length.
- Make ingestion **asynchronous**: `POST /documents` returns `202 Accepted` with a `doc_id` immediately; a background worker does the actual extraction. The UI/API polls or the demo just shows a status field. This alone solves "large PDFs" from a UX standpoint — nothing blocks.
- For the *first pass* over a big document, use the **Claude Batch API** (50% cheaper, high concurrent throughput, designed for exactly this — see `02-TRD.md` §4). For a single newly-uploaded document where a user is waiting live (e.g., during your demo video), use a fast synchronous model for a quick preview and let the batch job fill in the rest.
- Only pages that fail text-layer extraction (scanned/image pages) fall back to vision-based extraction — don't pay the expensive path for every page by default.

### 2.2 Many PDFs in the same knowledge layer
- This is a **candidate-generation** problem, not a storage problem. The fix is: never compare fact A to fact B unless a cheap vector-similarity lookup says they're plausibly about the same thing (same canonical entity + semantically similar attribute). This keeps comparison cost near-linear in the number of facts, regardless of how many documents contributed them.
- Canonicalize entities once (e.g., "Delhivery Limited," "Delhivery," "the Company" → one entity node) so facts about the same real-world thing cluster together across an arbitrary number of source documents.

### 2.3 A schema that evolves dynamically as new kinds of facts appear
- Don't define `Fact` subtypes in code. Define one universal envelope:

  ```
  Fact {
    entity, attribute, value, value_type (number|date|string|enum|boolean),
    unit, time_scope {period_start, period_end, as_of_date, fiscal_year},
    qualifiers: {free-form key-values — e.g., "consolidation": "standalone"},
    fact_type,          // e.g. "financial_metric", "director_appointment", "address"
    confidence,
    evidence[]          // exact quotes + page numbers, see TRD §3
  }
  ```
- `fact_type` is **not** an enum in your code — it's a string the extraction model proposes per fact, checked against a **type registry** (a table of previously-seen types + their embedding). If a new fact doesn't match any existing type above a similarity threshold, it's registered as a new type automatically. This is how the schema "evolves": the registry grows from data, the code never changes. Full detail in `02-TRD.md` §3.3.

### 2.4 New documents incrementally, without rebuilding all existing knowledge
- This is a **direct consequence** of candidate generation via vector search (§2.2): ingesting document N+1 only requires (a) extracting its own facts, (b) querying the *existing* vector index for matches, (c) running reconciliation only on the new-vs-existing candidate pairs. Nothing about documents 1..N is touched or reprocessed.
- Use content-hash-based idempotency (hash of PDF bytes or first-page text) so re-uploading the same file is a no-op rather than a duplicate.

---

## 3. Tech Stack Optimization Matrix

### 3.1 Where your current stack should carry the load
Assuming a Python-comfortable candidate:

| Layer | Recommendation | Why |
|---|---|---|
| PDF text/table extraction | `PyMuPDF` (fitz) + `pdfplumber` for tables | Fast, page-accurate, gives you exact character/page offsets for grounding without extra work |
| Backend API | FastAPI | Async-native (matters for background ingestion jobs), automatic OpenAPI docs = your "simple API" requirement for free |
| Background jobs | FastAPI `BackgroundTasks` for the prototype; upgrade to a real queue (RQ/Celery + Redis) only if you have time — see phasing in §6 | Matches "smaller, understandable" guidance; a full queue is a brownie-point nice-to-have, not core |
| Embeddings | `voyage-3` (Voyage AI, Anthropic's recommended embedding partner) or a local `sentence-transformers` model if you want zero external dependency | Keeps the whole stack inside one vendor relationship if using Voyage; local model removes an API key entirely if you want zero-cost embeddings |
| Frontend | Minimal React (Vite) or even server-rendered Jinja2 + HTMX | The brief explicitly does not reward UI polish — a fact browser + evidence viewer is enough |

### 3.2 Storage decision: Postgres + pgvector, not Neo4j — final

Given the actual constraint (short time to build, one person, evaluated on reasoning legibility over infra breadth), the graph-DB question resolves cleanly rather than staying open:

- **Facts and their relationships are representable as two relational tables** (`facts`, `fact_relationships` with a `relationship` column) with zero loss of query power at this project's scale. "Find everything that contradicts fact X" is `SELECT * FROM fact_relationships WHERE fact_a_id = X AND relationship = 'contradicts'` — not meaningfully harder than the equivalent Cypher, and something you can write and debug without learning a new query language under deadline pressure.
- **pgvector on Supabase gives you the vector index in the same database** as the facts themselves — one connection string, one thing to keep running, one thing that can fail. Supabase's free tier (500 MB DB) comfortably holds a few thousand facts with embeddings; the project pausing after 7 days of inactivity is a non-issue if you keep building or ping it before a review.
- **What this costs you:** multi-hop graph traversal queries ("everything within 2 hops that indirectly conflicts") are the one genuine capability Neo4j has that a relational schema doesn't do as elegantly. This project's four required cases are all **1-hop** relationships (fact A vs. fact B, directly), so that capability isn't actually exercised by anything you need to demonstrate.
- **Verdict:** build on Postgres + pgvector only. If the core system is done with time to spare, a read-only Neo4j sync for the visualization brownie point is a reasonable *optional* addition (see `02-TRD.md` §3.1, now marked optional) — but it is not on the critical path, and the plan should not assume it happens.

### 3.3 LLM provider: OpenAI (verified against current API/pricing docs, Sept 2026)

Current OpenAI lineup, **GPT-5.6** family — **Sol** ($4/$20, prior flagship, promotional pricing through Nov 21 2026), **Terra** ($2/$12, balanced), **Luna** ($0.20/$1.20, cost/volume-optimized) — plus older GPT-5.x and GPT-5 nano ($0.05/$0.40) still live. Batch API halves every rate; cached input is a further ~90% off on repeated context.

**Model split (mirrors the Haiku/Sonnet split in the original plan, mapped onto OpenAI's current ladder):**
- **Bulk per-page extraction → GPT-5.6 Luna, via Batch API.** This is the many-calls, low-judgment stage (turn page text/tables into structured `Fact` JSON) — Luna's price point ($0.20/$1.20, effectively $0.10/$0.60 batched) makes the full 205-page starter corpus cost cents, matching the original "cost is not the constraint" conclusion. Escalate a page-batch to **GPT-5.6 Terra** if a page has clear tabular-data signal but Luna returns zero facts (same cheap heuristic as the original plan).
- **Cross-document reconciliation → GPT-6 Sol.** This is the low-volume, high-judgment stage (is this a contradiction or a scope/unit/time difference?) — worth paying for the strongest available model since it's the smallest number of calls and the part the rubric explicitly weights most.
- **Structured Outputs** (JSON-schema strict mode) is supported across the whole current GPT-5.x/6.x lineup and composes with the Batch API exactly like the original Claude-based plan assumed — no loss of capability there.

**The one real gap versus the original Claude-based plan — evidence grounding.** OpenAI's API does not have Claude's native PDF-citation feature (a `cited_text` + location returned automatically alongside each extracted field). This has to be built explicitly rather than assumed:
1. Ask the model, in the extraction schema itself, for a `verbatim_quote` field per fact — instruct it explicitly to copy text exactly, not paraphrase.
2. **Validate it server-side**: after extraction, check that `verbatim_quote` (whitespace-normalized) actually appears as a substring of that page's raw extracted text (from `pdfplumber`/`PyMuPDF`, not from the model). If it doesn't match, either retry once or mark the fact's evidence as low-confidence rather than silently trusting an ungrounded quote.
3. This validator is worth building well — it's a legitimate, honest source for the **required extraction-failure case** (FR-17 in the PRD): a model occasionally paraphrasing instead of quoting verbatim is a real, demonstrable failure mode you caught and handled, not a contrived one.

### 3.4 Cost sanity check
For the three starter PDFs (~205 pages combined) plus test uploads: bulk extraction on **GPT-5.6 Luna via Batch** (≈$0.10/$0.60 per MTok) plus a few hundred reconciliation calls on **GPT-6 Sol** standard rate comes in at a few dollars total, even with retries and iteration.

---

## 4. System Architecture & Design
See `02-TRD.md` for the full data-flow diagram, API surface, storage schema, and deployment blueprint. Summary of the pipeline:

```
PDF upload → page-level text/table extraction (PyMuPDF/pdfplumber)
  → LLM structured extraction (GPT-5.6 Luna, batched)
  (facts + verbatim_quote + page ref, quote validated against raw page text)
  → entity canonicalization → embed (entity+attribute) → upsert to Postgres + pgvector
  → candidate generation (pgvector kNN against existing facts, same-entity filter)
  → LLM reconciliation call on candidate pairs (GPT-6 Sol: corroborate / contradict /
     reconcile / unrelated + natural-language explanation)
  → persist as relationship rows
  → API/UI surfaces facts, evidence, and relationship explanations
```

---

## 5. Full-Stack & Deployment Blueprint
Summary (full detail + verified free-tier numbers in `02-TRD.md` §6):

- **Backend (FastAPI + worker)** → Render free web service (750 hrs/month, sleeps after 15 min idle — acceptable for a graded prototype, not for production).
- **Fact store + vector index** → Supabase Postgres + `pgvector` — the only store in the plan (see §3.2).
- **Object storage for original PDFs** (needed to render evidence snippets against the source page) → Cloudflare R2 free tier (10 GB, zero egress fees, no time-based expiry).
- **Frontend** → Vercel Hobby (100 GB bandwidth, generous function invocations; keep any heavy processing off Vercel's functions given the 10–60s timeout — call out to your Render backend instead).
- **LLM** → OpenAI API directly (Batch API for bulk extraction on GPT-5.6 Luna, standard API for GPT-6 Sol reconciliation calls during the demo).

Total infra cost: **$0** on infrastructure, entirely inside free tiers, plus a few dollars of OpenAI usage. Main operational caveat is cold-starts/inactivity-pauses on Render/Supabase — solvable with a documented "give it up to a minute to wake up" note or a lightweight keep-alive job.

---

## 6. Actionable Groundwork Roadmap

**Phase 0 — Prove the hardest bet first (½–1 day).** Before any infra: write one script that takes 3–5 pages of one PDF, sends them to Claude with a tool-use schema for facts + citations, and confirms you get back structured facts with exact verbatim evidence and page numbers. This is the single riskiest assumption in the whole plan — validate it before building anything around it.

**Phase 1 — Core loop, single document (1–2 days).** Extraction → storage → a `/documents/{id}/facts` endpoint that returns facts with evidence. No reconciliation yet, no graph yet — plain Postgres is fine here. Get this fully working and legible before adding anything else.

**Phase 2 — Cross-document reconciliation (1–2 days).** Add entity canonicalization, embeddings, candidate generation, and the LLM reconciliation call. This is where the four required demo cases come from — run it across the two starter datasets and go hunting for the corroboration, contradiction, reconciled-by-context, and failure examples the submission requires. Write down the failure case honestly; it's a required deliverable, not a bug to hide.

**Phase 3 — Throughput + polish (1 day, optional/parallel).** Add Batch API processing for large-PDF throughput, tighten the quote-validation heuristic, and — only if genuinely ahead of schedule — a read-only Neo4j sync purely for the visualization brownie point (never load-bearing for the core reasoning). This order matters: infrastructure sophistication on top of broken reasoning scores worse than simple infrastructure with correct, well-explained reasoning.

**Phase 4 — UI, demo video, README (½–1 day).** A fact browser + an evidence panel + a relationships tab is enough UI. Script the 3-minute video around the four required cases specifically — don't do a general tour. Write the README sections the brief asks for verbatim (Setup, Video, Approach, Limitations, Additional Notes), and be honest in "Limitations" — the brief explicitly rewards this ("Be honest about what works, what does not").

**Groundwork checklist to start today:**
- [ ] Confirm the OpenAI key works, and validate the extraction → quote-check loop on one sample page before building anything around it — this is the single riskiest assumption now that Claude's native citations aren't available (see §3.3).
- [ ] Stand up Supabase (Postgres + pgvector enabled) — this is the only store to provision, no Neo4j step to wait on.
- [ ] Pick your embedding model (`text-embedding-3-small` is the cheap default at $0.02/MTok) and confirm dimension count before designing the vector index.
- [ ] Create the Render + Vercel + Supabase accounts now (free-tier signups can have delays/verification steps).
- [ ] Set aside a *third* PDF (not from either starter folder) early, to sanity-check "does this generalize" before submission — the brief tells you they will test with unseen documents.
