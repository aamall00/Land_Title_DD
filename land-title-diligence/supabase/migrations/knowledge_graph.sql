-- ============================================================
-- Knowledge Graph: entities, relationships, canonical_entities
-- Run this in your Supabase SQL Editor (or via supabase db push)
-- ============================================================

-- Ensure pgcrypto is available for uuid_generate_v4()
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── canonical_entities ─────────────────────────────────────────────────────
-- One row per distinct (entity_type, normalised_value) pair.
-- Used for entity resolution across multiple documents.

CREATE TABLE IF NOT EXISTS canonical_entities (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type   TEXT NOT NULL,
    canonical_val TEXT NOT NULL,   -- normalised form: uppercase + stripped
    aliases       JSONB NOT NULL DEFAULT '[]'::jsonb,  -- surface forms seen
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entity_type, canonical_val)
);

-- ── entities ───────────────────────────────────────────────────────────────
-- One row per entity occurrence extracted from a document.

CREATE TABLE IF NOT EXISTS entities (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID NOT NULL REFERENCES documents(id)  ON DELETE CASCADE,
    property_id   UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    entity_type   TEXT NOT NULL,
    value         TEXT NOT NULL,   -- extracted surface form
    canonical_id  UUID REFERENCES canonical_entities(id) ON DELETE SET NULL,
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,  -- unit, confidence, notes
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_entities_property_id  ON entities(property_id);
CREATE INDEX IF NOT EXISTS idx_entities_document_id  ON entities(document_id);
CREATE INDEX IF NOT EXISTS idx_entities_entity_type  ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_canonical_id ON entities(canonical_id);

-- ── relationships ──────────────────────────────────────────────────────────
-- Directed edges between two entity occurrences within a document.

CREATE TABLE IF NOT EXISTS relationships (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID NOT NULL REFERENCES documents(id)  ON DELETE CASCADE,
    property_id   UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    source_entity UUID NOT NULL REFERENCES entities(id)   ON DELETE CASCADE,
    target_entity UUID NOT NULL REFERENCES entities(id)   ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    attributes    JSONB NOT NULL DEFAULT '{}'::jsonb,  -- direction, date, amount, etc.
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_relationships_property_id  ON relationships(property_id);
CREATE INDEX IF NOT EXISTS idx_relationships_document_id  ON relationships(document_id);
CREATE INDEX IF NOT EXISTS idx_relationships_source       ON relationships(source_entity);
CREATE INDEX IF NOT EXISTS idx_relationships_target       ON relationships(target_entity);
CREATE INDEX IF NOT EXISTS idx_relationships_type         ON relationships(relation_type);

-- ── Row-Level Security (mirror the pattern from documents/properties) ──────
-- Enable RLS so service-role key bypasses it while anon/user keys are blocked.

ALTER TABLE canonical_entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE entities            ENABLE ROW LEVEL SECURITY;
ALTER TABLE relationships       ENABLE ROW LEVEL SECURITY;

-- Allow the service role full access (service role bypasses RLS by default,
-- but these explicit policies are useful when using the anon key in scripts).
CREATE POLICY "service_role_all_canonical" ON canonical_entities
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_entities" ON entities
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_relationships" ON relationships
    FOR ALL USING (true) WITH CHECK (true);
