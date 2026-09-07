# Product Requirements Document
## Fact Knowledge Layer — Superjoin VIT 2026 Engineering Intern Assignment

---

## 1. Purpose & Framing
Build a system that turns a set of PDFs into a queryable layer of **grounded, cross-referenced facts** — where every fact points to its exact source evidence, and every pair of related facts across documents is classified as corroborating, contradicting, or reconciled-by-context, with a stated reason.

This PRD treats the **hiring evaluator** as the primary user: they will upload an unfamiliar PDF, look at the output, and judge whether the extraction is meaningful, whether the evidence links are real and precise, and whether the reasoning about relationships is sound and explained. Everything in this document is written against that lens.

## 2. Users

| User | Need |
|---|---|
| Evaluator (primary) | Upload a new PDF (possibly outside the starter datasets) and get facts + evidence + relationships without touching code or config |
| You, during development | Inspect intermediate extraction output to debug bad facts before they reach reconciliation |
| Hypothetical downstream user (framing only, not built) | Ask "does this number check out against other sources" and get a sourced answer |

## 3. In Scope — Functional Requirements

### 3.1 Ingestion
- **FR-1**: Accept a PDF via API (`POST /documents`) or UI upload. Support the three provided PDFs and arbitrary unseen PDFs of a similar nature (financial/institutional reports).
- **FR-2**: Return immediately with a document ID and a processing status; extraction happens asynchronously. The caller must be able to poll for completion (`GET /documents/{id}`).
- **FR-3**: No behavior in the ingestion path may reference a specific filename, a specific document title, or a hard-coded section list. Document type/sections are to be *inferred*, not looked up from a table keyed by filename.

### 3.2 Fact extraction
- **FR-4**: Extract facts as structured records: an entity, an attribute/relationship, a value (typed), an optional unit, an optional time scope (period or as-of date), and free-form qualifiers for anything else that affects meaning (e.g., "consolidated" vs. "standalone," "provisional" vs. "revised").
- **FR-5**: Each fact must be assigned a `fact_type` label. This label set is **not fixed in code** — new types must be able to appear without a code change (see §5, dynamic schema).
- **FR-6**: The system should extract facts from narrative text *and* from tables (financial statements, macro data tables) — table-only extraction is not acceptable given both starter datasets are table-heavy.

### 3.3 Evidence grounding
- **FR-7**: Every fact must carry at least one evidence record: a verbatim quoted span (not a paraphrase), the source document ID, and the page number the quote appears on.
- **FR-8**: The UI/API must be able to show the evidence quote to the evaluator without requiring them to go find the sentence themselves — this is the difference between "grounded" and "trust me."

### 3.4 Cross-document reconciliation
- **FR-9**: For any two facts about the same real-world entity and comparable attribute (possibly from different documents), the system must be able to classify their relationship as one of: **corroborates**, **contradicts**, **reconciled by context** (with a stated reason — e.g., different time period, different scope/consolidation basis, different units), or **not comparable / unrelated**.
- **FR-10**: Every relationship classification must include a short natural-language explanation, not just a label — this is required for the demo cases and is explicitly called out in the brief as the evaluated part.
- **FR-11**: Entities referred to differently across documents (e.g., "Delhivery Limited" vs. "Delhivery," or two differently formatted addresses for the same location) must be resolved to the same canonical entity where evidence supports it, so their facts can actually be compared.

### 3.5 Interface
- **FR-12**: A simple API (documented, e.g., via OpenAPI/Swagger) sufficient for the evaluator to upload a PDF and retrieve facts, evidence, and relationships programmatically.
- **FR-13**: A lightweight UI is required only insofar as it makes the four demo cases inspectable without reading raw JSON; it is not evaluated on visual polish.

### 3.6 The four required demonstration cases
- **FR-14**: At least one fact **corroborated across documents**, shown with both pieces of evidence and the system's stated basis for calling it corroboration.
- **FR-15**: At least one **genuine or likely contradiction**, shown with both pieces of evidence and the system's stated basis for calling it a contradiction (as opposed to a reconciled difference).
- **FR-16**: At least one **apparent contradiction explained by context** (time period, scope, or units), shown with both facts, the surface-level disagreement, and the reconciling explanation.
- **FR-17**: At least one documented **extraction or reasoning failure**, with an honest account of what went wrong and either a fix or a stated plan to fix it.

## 4. Non-Functional Requirements

| ID | Requirement | Rationale |
|---|---|---|
| NFR-1 | **No hard-coded facts, filenames, schemas, or document-specific rules** anywhere in the extraction or reconciliation code path | Explicit grading criterion; the evaluator will test with unseen PDFs |
| NFR-2 | The system must not require re-processing existing documents when a new document is added | Required for the "incremental ingestion" brownie point and for basic scalability |
| NFR-3 | Comparison cost must not scale quadratically with the number of facts in the system | Required for the "many PDFs" brownie point; also just good engineering |
| NFR-4 | Large PDFs (100 pages) must not block the API or cause request timeouts | Required for the "large PDFs" brownie point |
| NFR-5 | The fact schema must be able to represent new kinds of facts (e.g., a fact type never seen in the starter datasets) without a code deployment | Required for the "dynamic schema" brownie point |
| NFR-6 | The whole system must be reproducible by the evaluator from README instructions alone, with no paid account required to review it (sample output + video substitute for anything paid) | Explicit submission requirement |
| NFR-7 | Reasoning outputs (extraction, reconciliation) must degrade gracefully — a failed or low-confidence extraction should be visible as such, not silently dropped or silently presented as ground truth | Ties directly to FR-17 and to overall trustworthiness of the system |

## 5. Design Constraints Carried from the Brief
- The documents themselves should determine what counts as a fact and how it's represented — the brief is explicit that "your schema... [is] entirely up to you," but also that it should be document-driven, not imposed.
- A graph database or a visualization is explicitly **not**, by itself, an acceptable answer to the assignment — the reasoning behind facts/relationships is the deliverable, and infra choices should serve legibility of that reasoning, not substitute for it.
- Sensible handling of ambiguity and uncertainty is graded — a fact or a relationship the system is unsure about should carry a confidence signal rather than being asserted with false certainty.

## 6. Out of Scope
- User authentication/multi-tenant access control (single-evaluator use case).
- Production-grade uptime, horizontal scaling, or SLAs — this is a prototype evaluated on approach and reasoning, not on load-bearing infrastructure.
- Support for non-PDF input formats (explicitly PDFs per the brief).
- A general-purpose RAG chatbot / question-answering interface over the documents — nice-to-have, not required, and shouldn't consume time that belongs to the four required cases.
- Full visual graph exploration UI — explicitly de-emphasized in the brief.

## 7. Success Metrics / Acceptance Criteria
Mapped directly to the brief's own "Before You Submit" checklist:

- [ ] Project runs end-to-end from documented instructions and accepts a new PDF via API or UI (not just the three starter files).
- [ ] Every returned fact has at least one evidence record with an exact quote and page number.
- [ ] At least one cross-document relationship of each of the three reasoning types (corroborate / contradict / reconcile) is demonstrable, plus one documented failure case.
- [ ] Uploading a PDF from outside either starter folder produces sensible (not necessarily perfect) facts with no code changes.
- [ ] README contains Setup & Run, Video Demo link (≤3 min), Approach, Limitations & Next Steps, and Additional Notes.
- [ ] No credentials are committed; if any paid service is used, sample output + video footage stand in for reviewer access.

## 8. Risks & Assumptions
- **Assumption**: candidate has (or will obtain) an LLM API key with document/vision input support; the reconciliation quality of this system is bounded by the LLM's reasoning quality, not by the surrounding infrastructure.
- **Risk**: free-tier services used for the deployed demo (Render, Neo4j AuraDB) sleep/pause after inactivity; the README and video should account for a cold-start delay so it doesn't read as a broken deployment.
- **Risk**: over-building infrastructure at the expense of extraction/reasoning quality is the most likely way to underperform on this specific rubric — see calibration note in `00-strategy-overview.md` §1.3.
- **Assumption**: "genuine or likely contradiction" in FR-15 permits a contradiction the system flags with appropriate uncertainty (not necessarily a 100%-certain factual error) — the brief's own examples (director status changing over time) suggest evaluators expect nuanced, not binary, judgments.
