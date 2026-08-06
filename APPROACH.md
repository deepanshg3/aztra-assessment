# Approach

## A. Problem Decomposition

The assessment requires answering four categories of business questions over structured and unstructured enterprise data for Suryaa Consumer Products. Rather than building a monolithic system, the problem was decomposed into five separable sub-problems:

1. **Routing** — Determine the question category (WHAT, WHY, WHAT_TO_DO, OUT_OF_DOMAIN) before any processing occurs. This allows early abstention for out-of-domain questions and avoids unnecessary LLM or database calls.

2. **SQL Reasoning** — Translate natural-language analytical questions into correct, safe SQL queries against a star-schema SQLite database containing product, geography, sales, target, stockout, and promotion data.

3. **Document Reasoning** — Retrieve relevant unstructured business documents (emails, visit notes, circulars, SOPs) using semantic similarity, providing supporting evidence for explanatory and advisory queries.

4. **Orchestration** — Coordinate the above modules into intent-specific pipelines. WHAT uses SQL only; WHY uses SQL plus document retrieval; WHAT_TO_DO uses SQL plus document retrieval and marks the result as pending human approval; OUT_OF_DOMAIN returns an immediate abstention.

5. **Response Generation** — Synthesise a final answer from the collected evidence (SQL rows and document text) using a separate LLM call, with citations and confidence scoring.

## B. Solution and Agentic Design

The implementation follows a modular pipeline architecture with a central orchestrator. Each module has a single responsibility and exposes a minimal interface.

### Pipeline Flow

```
                    Request
                       │
                       ▼
              Input Validation
                       │
                       ▼
            Intent Classification
                       │
      ┌─────────┬─────────┬──────────────┬
      ▼         ▼         ▼              ▼
    WHAT       WHY   WHAT_TO_DO   OUT_OF_DOMAIN
      │         │         │                │
 SQL Planner SQL Planner SQL Planner       │
      │         │         │                │
 SQL Validator SQL Validator SQL Validator │
      │         │         │                │
 SQL Executor SQL Executor SQL Executor    │
      │         │         │                │
      │   Doc Retriever Doc Retriever      │
      │          │         │               │
       Response Generator Response Generator
                │         │                │
         status=OK   status=PENDING        │
                │         │                │
      └─────────┴─────────┴────────────────┘
                       │
                       ▼
              AssessmentResponse
```

### Module Responsibilities

**Intent Classifier** — A dedicated LLM call with a strict prompt that classifies questions into exactly one of four intents. The prompt includes injection resistance instructions and outputs only valid JSON matching a Pydantic schema. This runs first, so out-of-domain questions never reach downstream systems.

**SQL Planner** — Takes the user question and the database schema summary, and calls the LLM to generate a single SQLite SELECT statement. The schema summary includes table structures, column descriptions, foreign key relationships, and business notes. The output is cleaned of markdown fences before validation.

**SQL Validator** — A deterministic (non-LLM) safety layer that checks the generated SQL. Rejects any query containing INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, or other mutation keywords. Rejects multi-statement queries, SQL comments, and queries that do not begin with SELECT or WITH. This is the primary hallucination and safety guard.

**SQL Executor** — Runs the validated query against the SQLite database using a row-factory connection. Returns results as a list of dictionaries. The database is pre-built from cleaned CSV data with foreign key constraints and indexes.

**Document Indexer** — Reads 30 text documents from `data/raw/docs/`, generates embeddings using Google's text-embedding-004 model via LangChain, and stores them in a persistent ChromaDB collection with cosine distance. The indexing is idempotent: already-indexed documents are skipped.

**Document Retriever** — Embeds the user question and queries ChromaDB for the top-3 most semantically similar documents. Returns filenames, content, and distance scores. Documents include emails about stockouts, visit notes about competitor activity, promo circulars, SOPs, and routine operational notes.

**Response Generator** — A final LLM call that receives the original question, the detected intent, the SQL results, and any retrieved documents. It produces a JSON response containing an answer, a list of citation filenames, and a confidence score. The prompt instructs it to use only the provided evidence and never invent facts.

**Evaluation** An automated evaluation harness executes a representative set of business queries against the deployed API, records responses, latency and metadata, and produces a JSON report for manual qualitative evaluation.

### Why This Architecture

- **Separation of concerns** lets each module be developed, tested, and improved independently. The SQL validator and document retriever do not require an LLM. The orchestrator contains no SQL or prompt knowledge.
- **Deterministic safety layer** (SQL validator) runs before any database query, catching malformed or dangerous SQL regardless of LLM behaviour.
- **Output Validation** Every LLM response is validated against a strict Pydantic schema before it is accepted by downstream modules.

- **Early abstention** for out-of-domain questions avoids wasting LLM tokens and database resources.
- **Explicit PENDING_APPROVAL** status for recommendations meets the assessment requirement that no recommendation is executed without human authorisation.
- **Module reuse** — the same SQL pipeline and retrieval pipeline serve both WHY and WHAT_TO_DO intents, differing only in how the response generator uses them.

## C. Data Interaction Design

### Structured Data (SQLite)

The analytical database is built from eight cleaned CSV files organised into a star schema.

- **Dimension tables:** Product (`dim_sku`), Geography (`dim_geo`), Sales Representative (`dim_rep`), and Distributor (`dim_distributor`) provide descriptive business attributes.
- **Fact tables:** `fact_primary_sales` stores transactional sales records, while `fact_targets` stores planned sales targets for performance comparison.
- **Supporting tables:** `stockouts` and `promotions` capture operational events that enrich analytical and explanatory queries.



The database builder validates referential integrity before import, creates indexes on all foreign key columns, and enables foreign key enforcement after load. The build is idempotent.

Schema awareness is provided to the LLM via a `database_summary.py` module that describes every table, column, primary key, foreign key, and business rule in a flat text format. This is injected into the SQL planning prompt.

SQL generation uses the LLM with the schema as context. The generated SQL is then cleaned of formatting artefacts and validated by the deterministic validator before execution.

### Unstructured Data (ChromaDB)

30 text documents are embedded using Google's text-embedding-004 model and stored in a persistent ChromaDB collection with cosine distance as the similarity metric.

During retrieval, the user question is embedded using the same model, and ChromaDB returns the top-3 documents by cosine similarity. Results include the filename, full text content, and distance score, which are passed to the response generator as evidence.

The embedding client includes exponential-backoff retry for transient API failures and caches the model instance after initialisation.

## D. Risks and Trade-offs

### Hallucination Prevention

- Every LLM prompt begins with a system instruction that restricts the assistant to the provided role, ignores injection attempts, and prohibits use of outside knowledge.
- The response generator prompt explicitly instructs the model to use only the supplied evidence and to state when evidence is insufficient.
- SQL results and retrieved documents are injected as plain text into the prompt, making the evidence visible to the LLM.

### SQL Safety

- The deterministic SQL validator is the primary defence against hallucinated or malicious SQL. It runs before every query execution.
- Only SELECT and WITH statements are allowed. All mutation keywords are blocked at the regex level.
- Multi-statement queries and SQL comments are rejected.
- The LLM prompt for SQL generation also includes safety instructions, but the validator is the authoritative gate.

### Recommendation Approval

- Every WHAT_TO_DO response has `status` set to `PENDING_APPROVAL` by the orchestrator, not by the LLM. The response generator prompt does not control this field; the orchestrator always overrides it. This ensures the approval requirement cannot be bypassed through prompt manipulation.

### Abstention Behaviour

- The OUT_OF_DOMAIN pipeline returns a fixed message, an empty citation list, confidence of 1.0, and status `ABSTAINED`. No SQL or LLM calls are made. The intent classifier is the single gatekeeper.

### Retrieval Limitations

- ChromaDB retrieves exactly the top-3 documents. If the relevant document is the 4th closest, it will not appear. The embedding model's quality and the diversity of indexed documents determine retrieval effectiveness.
- The document corpus includes 19 routine notes containing "no exceptions" content, which may produce false positive retrievals for many queries.

### Future Improvements

- Add multi-turn conversation context to support follow-up questions.
- Implement SQL execution result caching for repeated queries.
- Add an explicit NLI (natural language inference) step to verify that retrieved documents actually support the generated answer.
- Expand the evaluation harness to compare generated answers against golden reference answers.
- Replace the LLM-generated SQL with a slot-filling or grammar-based approach for higher reliability on well-defined query patterns.
- Add streaming responses for long-running queries.
