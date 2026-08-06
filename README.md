# Retail Sales Analytics Assistant

An AI-powered question-answering system for Suryaa Consumer Products FMCG sales data. Answers analytical, explanatory, and advisory questions over structured SQLite data and unstructured business documents.

## Key Features

- **Intent Classification** — Routes every question to one of four pipelines: WHAT (analytical), WHY (explanatory), WHAT_TO_DO (advisory), or OUT_OF_DOMAIN (abstention).
- **LLM-Generated SQL** — Produces validated SELECT queries from natural language using the database schema as context.
- **Semantic Document Retrieval** — Embeds business documents (emails, visit notes, promo circulars) into ChromaDB and retrieves the top-3 most relevant results per query.
- **Recommendation Guard** — Every WHAT_TO_DO response returns with `status: PENDING_APPROVAL` to enforce human approval.
- **Safety-First Design** — SQL validator blocks mutations, multi-statement queries, comments, and forbidden keywords. LLM prompts include injection resistance instructions. Input validation enforces length and non-empty constraints.
- **Abstention Behaviour** — Questions outside the available enterprise data are refused immediately without any SQL or LLM invocation.

## System Architecture

```
User Request → FastAPI → Input Validation → Intent Classifier
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    ▼                           ▼                           ▼
                 WHAT                        WHY                    WHAT_TO_DO
                    │                           │                           │
              SQL Planner                 SQL Planner                 SQL Planner
              SQL Executor               SQL Executor               SQL Executor
                                               │                           │
                                       Doc Retriever               Doc Retriever
                    │                           │                           │
              Response Gen.              Response Gen.              Response Gen.
              (status=OK)                (status=OK)           (status=PENDING_APPROVAL)

OUT_OF_DOMAIN → Immediate abstention (no SQL, no LLM)
```

For WHY and WHAT_TO_DO intents, the SQL results and retrieved documents are passed together to the response generator, which synthesises a final answer grounded only in the provided evidence.

## Repository Structure

```
├── main.py                     # FastAPI server entry point
├── README.md
├── APPROACH.md
├── ARTEFACT.md
├── requirements.txt
├── .env.example
├── src/
│   ├── api/
│   │   └── app.py              # FastAPI routes (GET /health, POST /ask)
│   ├── core/
│   │   ├── settings.py         # Env-based config (API key, model names)
│   │   ├── input_validation.py # Request validation
│   │   └── logger.py           # Structured logging
│   ├── schemas/
│   │   ├── intent.py           # IntentClassification (Pydantic)
│   │   └── response.py         # AssessmentResponse (Pydantic)
│   ├── llm/
│   │   ├── client.py           # Reusable Google Gemini client 
│   │   └── prompts.py          # Intent classification prompt template
│   ├── routing/
│   │   └── intent_classifier.py
│   ├── orchestrator/
│   │   └── orchestrator.py     # Central pipeline coordinator
│   ├── sql/
│   │   ├── planner.py          # LLM-based SQL generation
│   │   ├── validator.py        # Deterministic SQL safety checks
│   │   ├── executor.py         # SQLite query execution
│   │   ├── prompts.py          # SQL generation prompt template
│   │   └── database_summary.py # Schema summary fed to the LLM
│   ├── rag/
│   │   ├── embedding_client.py # Google Gemini embeddings via LangChain
│   │   ├── indexer.py          # Document → ChromaDB indexing pipeline
│   │   └── retriever.py        # Semantic search (top-3)
│   ├── response_generator/
│   │   ├── generator.py        # Final answer synthesis
│   │   └── prompts.py          # Response generation prompt template
│   ├── database/
│   │   ├── schema.py           # DDL, indexes, FK metadata
│   │   └── builder.py          # Idempotent SQLite build from cleaned CSVs
│   ├── data_cleaning/
│   │   ├── config.py           # Cleaning rules and constants
│   │   ├── cleaners.py         # Field-level normalization functions
│   │   └── pipeline.py         # Deterministic cleaning orchestration
│   └── evaluation/
│       ├── questions.py        # 20 predefined test questions
│       └── runner.py           # Black-box HTTP evaluation harness
├── data/
│   ├── raw/                    # Raw CSV datasets + 30 txt documents
│   ├── cleaned/                # Normalized, deduplicated CSV output
│   ├── database/suryaa.db      # SQLite database
│   └── vector_db/              # ChromaDB persistent store
└── evaluation_results/         # Timestamped evaluation JSON output
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key (required) | — |
| `GEMINI_MODEL` | Gemini model name | `gemini-3.1-flash-lite` |
| `EMBEDDING_MODEL` | Embedding model name | `gemini-embedding-001` |

## Running Locally

Once the environment variables are configured, start the API server:

```bash
python main.py
```

The server will be available at:

```
http://127.0.0.1:8000
```

Interactive API documentation is available at:

```
http://127.0.0.1:8000/docs
```

## API

### `GET /health`

```json
{"status": "healthy"}
```

### `POST /ask`

**Request:**
```json
{"question": "Why did GlucoJoy sales decrease in Delhi?"}
```

**Response:**
```json
{
    "answer": "GlucoJoy sales in Delhi decreased due to a supplier delay ...",
    "intent": "WHY",
    "citations": ["email_01.txt"],
    "confidence": 0.97,
    "status": "OK"
}
```

**Status values:**
| Status | Meaning |
|--------|---------|
| `OK` | Query completed successfully (WHAT, WHY) |
| `PENDING_APPROVAL` | Recommendation requires human approval (WHAT_TO_DO) |
| `ABSTAINED` | Question was out of domain (OUT_OF_DOMAIN) |

## Evaluation

The evaluation runner sends 20 questions (5 per intent) to the running API and records latency and response data:

```bash
python -m src.evaluation.runner
```

Results are saved to `evaluation_results/evaluation_<timestamp>.json`. The last run achieved 20/20 successful responses with an average latency of ~8.2 seconds.

## Deployment

The application is deployed on Render as a FastAPI web service using Uvicorn. The repository includes the pre-built SQLite database and persistent ChromaDB vector store, allowing the application to start immediately once the required environment variables are configured.

## Live Demo

**Base URL**

https://aztra-assessment.onrender.com

**Interactive API Documentation (Swagger UI)**

https://aztra-assessment.onrender.com/docs

**Health Check**

https://aztra-assessment.onrender.com/health

**Inference Endpoint**

POST https://aztra-assessment.onrender.com/ask

## Technology Stack

| Layer | Technology |
|-------|-----------|
| API Framework | FastAPI + Uvicorn |
| LLM | Google Gemini 3.1 Flash Lite  |
| Embeddings | Google gemini-embedding-001 via LangChain |
| Structured Storage | SQLite |
| Vector Storage | ChromaDB |
| Validation | Pydantic v2 |
| Data Processing | Python standard library + pandas |
| Deployment | Render |
