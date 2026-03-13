# BhumiCheck — Bangalore Land Title Due Diligence

AI-powered land title verification for Karnataka properties. Upload EC, RTC, Sale Deed, Khata, and other documents; ask questions in English or Kannada; generate automated due diligence reports.

---

## Architecture

```
Frontend (React + Tailwind + Vite)
    ↕ HTTPS / Vite proxy
Backend (FastAPI + Python)
    ├── OCR Service        (Tesseract/Textract — Kannada + English)
    ├── Embedding Service  (multilingual-e5-large, 768-dim)
    ├── Vector Service     (Supabase pgvector, hybrid search)
    ├── LLM Service        (Claude Sonnet — Q&A + due diligence checks)
    └── Report Service     (6 structured checks → risk score + report)
    ↕
Supabase
    ├── PostgreSQL         (properties, documents, queries, reports)
    ├── pgvector           (embeddings table with IVFFlat index)
    ├── Storage            (raw PDF/image files — permanent, per-user)
    └── Auth               (email/password; JWT passed to backend)
```

---

## Features

| Feature | Details |
|---|---|
| **Document Types** | EC, RTC/Pahani, Sale Deed, Khata, Mutation, Sketch, Court, BBMP/BDA approvals |
| **OCR** | Tesseract (free, local) or AWS Textract; both support Kannada + English |
| **Embeddings** | `intfloat/multilingual-e5-large` — same vector space for Kannada & English |
| **Search** | Hybrid: pgvector cosine similarity + doc_type metadata filter |
| **Q&A** | Claude Sonnet grounded in retrieved chunks; cites source document |
| **Auto-classify** | Filename + text heuristics detect EC vs RTC vs Sale Deed etc. |
| **Metadata extraction** | Regex extracts Survey No., Khata No., area, year, taluk from OCR text |
| **Due Diligence Report** | 6 checks: Title Chain · Encumbrances · Litigation · Khata · Area · Approval |
| **Risk Score** | 0–100 score + LOW/MEDIUM/HIGH/CRITICAL level |
| **Auth** | Supabase email auth; row-level security isolates each user's data |
| **Storage** | Permanent — files never deleted unless user explicitly removes them |

---

## Project Structure

```
land-title-diligence/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, routes
│   │   ├── config.py            # Pydantic Settings (reads .env)
│   │   ├── database.py          # Supabase client singleton
│   │   ├── models/schemas.py    # Pydantic request/response models
│   │   ├── api/routes/
│   │   │   ├── properties.py    # CRUD for properties
│   │   │   ├── documents.py     # Upload, OCR, classify, delete
│   │   │   ├── queries.py       # Q&A with RAG
│   │   │   └── reports.py       # Due diligence report generation
│   │   ├── services/
│   │   │   ├── ocr_service.py       # Tesseract / Textract
│   │   │   ├── embedding_service.py # multilingual-e5-large + chunking
│   │   │   ├── vector_service.py    # pgvector store + search
│   │   │   ├── llm_service.py       # Claude Q&A + structured checks
│   │   │   └── report_service.py    # Orchestrates all 6 DD checks
│   │   └── utils/
│   │       └── document_classifier.py  # Regex-based type detection
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Auth.jsx           # Sign in / sign up
│   │   │   ├── Dashboard.jsx      # Property list
│   │   │   └── PropertyDetail.jsx # 3-tab view: Docs / Q&A / Report
│   │   ├── components/
│   │   │   ├── layout/Header.jsx
│   │   │   ├── property/{Card,Form}.jsx
│   │   │   ├── documents/{Upload,List}.jsx
│   │   │   ├── query/QueryInterface.jsx
│   │   │   └── report/ReportView.jsx
│   │   ├── lib/{supabase.js,api.js}
│   │   └── hooks/useAuth.js
│   └── .env.example
└── supabase/
    └── migrations/001_initial_schema.sql
```

---

## Setup

### 1. Supabase

1. Create a new project at [supabase.com](https://supabase.com)
2. Run the migration in the SQL editor:
   ```sql
   -- Copy and paste supabase/migrations/001_initial_schema.sql
   ```
3. Create a storage bucket named `land-documents` (private)
4. Add the storage policies from the SQL comment in the migration file

### 2. Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Tesseract + Kannada language data
# Ubuntu/Debian:
sudo apt install tesseract-ocr tesseract-ocr-kan

# macOS:
brew install tesseract
# Download kan.traineddata to /usr/local/share/tessdata/

# Copy and fill environment
cp .env.example .env
# Edit .env with your Supabase keys and Anthropic API key

# Download embedding model (first run will auto-download ~560MB)
# Or pre-download:
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-large')"

# Run the API
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend

npm install

cp .env.example .env
# Edit .env with your Supabase URL and anon key

npm run dev
```

App: http://localhost:5173

---

## How It Works

### Document Upload Flow

```
Upload PDF/Image
      ↓
Store in Supabase Storage (permanent path: /{user_id}/{property_id}/{filename})
      ↓ (background task)
OCR (Tesseract kan+eng or AWS Textract)
      ↓
Document type classifier (filename + text regex patterns)
      ↓
Metadata extraction (survey no, khata, area, year, taluk)
      ↓
Chunking (800 chars, 150 overlap, sentence-aware)
      ↓
multilingual-e5-large embedding (768-dim, normalized)
      ↓
Store chunks in pgvector embeddings table
      ↓
Mark document status = 'ready'
```

### Q&A Flow

```
User question
      ↓
embed_query('query: ' + question)  — multilingual-e5-large
      ↓
match_embeddings() — pgvector cosine search, filtered by property_id
                      (optionally filter by doc_type)
      ↓
Top 6 chunks → Claude Sonnet
      ↓
Answer with citations + source document names
      ↓
Saved to queries table
```

### Due Diligence Report

```
6 parallel checks:
  Title Chain    → EC + Sale Deed + Mutation chunks
  Encumbrances   → EC chunks
  Litigation     → Court + EC + Sale Deed chunks
  Khata Match    → Khata + Sale Deed + RTC chunks
  Area Match     → RTC + Sale Deed + Sketch chunks
  Layout Approval→ BBMP + BDA chunks

Each check → Claude Sonnet → JSON {status, summary, findings, sources}

Missing document detection (which of EC/RTC/Deed/Khata/Mutation/Sketch absent?)

Risk score: weighted by FAIL/WARN/MISSING statuses + red flag count
Risk level: LOW (0-20) | MEDIUM (21-45) | HIGH (46-70) | CRITICAL (71-100)

Persisted to reports table
```

---

## Karnataka-Specific Design Decisions

- **Survey Number as primary filter** — every vector search scopes to `property_id` which maps to a specific Sy. No. / Khata No.
- **30-year title chain verification** — the Title Chain check explicitly prompts Claude to verify unbroken ownership for 30 years as required under Karnataka law
- **Kaveri EC format awareness** — EC patterns tuned to Karnataka's Kaveri sub-registrar portal output
- **Bhoomi RTC format** — RTC extraction patterns match Karnataka's bhoomi.karnataka.gov.in format
- **Taluk/Hobli/Village hierarchy** — stored as separate structured fields for precise filtering
- **Kannada + English embedding space** — multilingual-e5-large maps both scripts to the same semantic space, so a query in English can retrieve Kannada document chunks

---

## Technology Choices

| Component | Choice | Alternative |
|---|---|---|
| Embeddings | `multilingual-e5-large` (768-dim) | LaBSE, paraphrase-multilingual |
| Vector DB | Supabase pgvector | Pinecone, Weaviate, Qdrant |
| OCR | Tesseract kan+eng (local) | AWS Textract (better accuracy) |
| LLM | Claude Sonnet 4.6 | GPT-4o |
| Auth + DB | Supabase | Firebase + separate Postgres |
| File Storage | Supabase Storage | AWS S3 |

---

## Disclaimer

BhumiCheck provides AI-assisted analysis for reference only. The output should not be treated as legal advice. All findings must be verified by a licensed property lawyer and registered sub-registrar records before any property transaction.
