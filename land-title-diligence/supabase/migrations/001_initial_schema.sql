-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- PROPERTIES — Central entity; all docs/queries belong to one
-- ============================================================
CREATE TABLE properties (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  property_name TEXT NOT NULL,
  survey_number TEXT,               -- Sy. No. / Survey Number
  khata_number  TEXT,
  taluk         TEXT,               -- e.g. Yelahanka, Bangalore North
  hobli         TEXT,
  village       TEXT,
  district      TEXT DEFAULT 'Bangalore Urban',
  total_area    TEXT,               -- e.g. "2400 sq ft", "0.5 acres"
  address       TEXT,
  notes         TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_properties_user ON properties(user_id);
CREATE INDEX idx_properties_survey ON properties(survey_number);

-- ============================================================
-- DOCUMENTS — Each uploaded file linked to a property
-- ============================================================
CREATE TABLE documents (
  id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  property_id    UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  user_id        UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  -- File info
  original_name  TEXT NOT NULL,
  file_url       TEXT NOT NULL,       -- Supabase Storage path
  file_size      INTEGER,
  mime_type      TEXT,
  page_count     INTEGER,

  -- Classification
  doc_type       TEXT NOT NULL DEFAULT 'OTHER',
  -- EC | RTC | SALE_DEED | KHATA | MUTATION | SKETCH |
  -- LEGAL_HEIR | COURT | BBMP_APPROVAL | BDA_APPROVAL | OTHER

  language       TEXT DEFAULT 'mixed', -- 'kannada' | 'english' | 'mixed'

  -- Extracted content
  ocr_text       TEXT,
  metadata       JSONB DEFAULT '{}',
  -- e.g. { survey_no, owner_name, year, taluk, ec_period, area, ... }

  -- Processing status
  status         TEXT DEFAULT 'pending',
  -- 'pending' | 'processing' | 'ready' | 'error'
  error_message  TEXT,

  uploaded_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_documents_property ON documents(property_id);
CREATE INDEX idx_documents_user ON documents(user_id);
CREATE INDEX idx_documents_type ON documents(doc_type);
CREATE INDEX idx_documents_status ON documents(status);

-- ============================================================
-- EMBEDDINGS — Vector chunks from documents (LaBSE / e5-large)
-- ============================================================
CREATE TABLE embeddings (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  document_id   UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  property_id   UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  chunk_index   INTEGER NOT NULL,
  chunk_text    TEXT NOT NULL,
  embedding     vector(768),          -- multilingual-e5-large dimension
  metadata      JSONB DEFAULT '{}',   -- { doc_type, page_num, survey_no, ... }
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_embeddings_document ON embeddings(document_id);
CREATE INDEX idx_embeddings_property ON embeddings(property_id);
-- IVFFlat index for approximate nearest-neighbour search
CREATE INDEX idx_embeddings_vector ON embeddings
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================
-- QUERIES — Saved Q&A history per property
-- ============================================================
CREATE TABLE queries (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  question    TEXT NOT NULL,
  answer      TEXT,
  sources     JSONB DEFAULT '[]',  -- [ {document_id, doc_type, chunk_text, score} ]
  tokens_used INTEGER,
  asked_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_queries_property ON queries(property_id);

-- ============================================================
-- REPORTS — Generated due diligence reports
-- ============================================================
CREATE TABLE reports (
  id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  property_id  UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  report_type  TEXT NOT NULL DEFAULT 'full_due_diligence',
  -- 'full_due_diligence' | 'title_chain' | 'risk_summary'

  -- Structured output
  content      JSONB NOT NULL DEFAULT '{}',
  -- {
  --   title_chain: { status, chain, gaps },
  --   encumbrances: { status, findings },
  --   litigation: { status, findings },
  --   khata_consistency: { status, findings },
  --   measurement_match: { status, findings },
  --   layout_approval: { status, findings },
  --   missing_documents: [ ... ],
  --   red_flags: [ ... ],
  --   overall_risk: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  -- }

  red_flags    JSONB DEFAULT '[]',
  risk_score   INTEGER,              -- 0-100
  risk_level   TEXT,                 -- 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  generated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_reports_property ON reports(property_id);

-- ============================================================
-- ROW-LEVEL SECURITY — Each user sees only their own data
-- ============================================================
ALTER TABLE properties  ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents   ENABLE ROW LEVEL SECURITY;
ALTER TABLE embeddings  ENABLE ROW LEVEL SECURITY;
ALTER TABLE queries     ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports     ENABLE ROW LEVEL SECURITY;

-- Properties
CREATE POLICY "Users manage own properties" ON properties
  USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- Documents
CREATE POLICY "Users manage own documents" ON documents
  USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- Embeddings (accessed via property/document ownership)
CREATE POLICY "Users access own embeddings" ON embeddings
  USING (property_id IN (
    SELECT id FROM properties WHERE user_id = auth.uid()
  ));

-- Queries
CREATE POLICY "Users manage own queries" ON queries
  USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- Reports
CREATE POLICY "Users manage own reports" ON reports
  USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- ============================================================
-- STORAGE BUCKET (run via Supabase dashboard or CLI)
-- ============================================================
-- INSERT INTO storage.buckets (id, name, public)
-- VALUES ('land-documents', 'land-documents', false);
--
-- CREATE POLICY "Users upload own docs" ON storage.objects
--   FOR INSERT WITH CHECK (
--     bucket_id = 'land-documents' AND
--     auth.uid()::text = (storage.foldername(name))[1]
--   );
-- CREATE POLICY "Users read own docs" ON storage.objects
--   FOR SELECT USING (
--     bucket_id = 'land-documents' AND
--     auth.uid()::text = (storage.foldername(name))[1]
--   );

-- ============================================================
-- HELPER FUNCTION: vector similarity search for a property
-- ============================================================
CREATE OR REPLACE FUNCTION match_embeddings(
  query_embedding vector(768),
  target_property_id UUID,
  match_count INT DEFAULT 6,
  doc_types TEXT[] DEFAULT NULL
)
RETURNS TABLE (
  id UUID,
  document_id UUID,
  chunk_text TEXT,
  metadata JSONB,
  similarity FLOAT
)
LANGUAGE SQL STABLE
AS $$
  SELECT
    e.id,
    e.document_id,
    e.chunk_text,
    e.metadata,
    1 - (e.embedding <=> query_embedding) AS similarity
  FROM embeddings e
  JOIN documents d ON d.id = e.document_id
  WHERE
    e.property_id = target_property_id
    AND (doc_types IS NULL OR d.doc_type = ANY(doc_types))
  ORDER BY e.embedding <=> query_embedding
  LIMIT match_count;
$$;
