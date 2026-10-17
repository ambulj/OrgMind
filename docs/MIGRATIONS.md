# OrgMind Domain Model Upgrade & Migration Guide (v0.2)

## 1. Domain Schema Specification

### A. Decision Node
- `id`: Unique identifier (e.g. `DEC_AUTH_2026_02`)
- `text`: Ratified policy or architectural decision statement
- `topic`: Domain keyword (e.g. `OAuth`, `Paynova`)
- `status`: `'current'` | `'superseded'` | `'rejected'`
- `valid_from`: Real-world effective start timestamp (ISO 8601)
- `valid_to`: Real-world superseded timestamp (ISO 8601 or empty string)
- `recorded_at`: System ingestion timestamp (ISO 8601)
- `confidence`: Extraction confidence score (float `0.0` to `1.0`)
- `confidence_tier`: UI mapped tier (`'High'`, `'Medium'`, `'Low'`)
- `extraction_run_id`: Unique identifier of the extraction job
- `extracted_by`: Ingestion source/model name (e.g. `'manual'`, `'ollama/qwen2.5-coder:14b'`)
- `review_status`: `'auto'` | `'pending'` | `'approved'` | `'rejected'`

### B. Source Node
- `id`: Unique source chunk identifier (e.g. `SRC_DOC_PKCE_01`)
- `content_hash`: Cryptographic SHA-256 hash of the original text snippet
- `uri`: Uniform Resource Identifier (e.g. `file://data/docs/oauth_pkce_spec.md`)
- `origin_type`: Origin classification (`'document'`, `'chat'`, `'incident'`, `'meeting_notes'`)
- `author`: Author Person ID or identifier
- `text_snippet`: Verbatim quote chunk (or tombstone placeholder if redacted)
- `visibility`: ACL array stored as JSON string (e.g. `'["all"]'` or `'["Admin", "Editor"]'`)
- `redacted`: Boolean flag (`true` if redacted tombstone, default `false`)
- `redacted_at`: Timestamp of redaction (or empty string)
- `redacted_by`: Actor who authorized redaction (or empty string)
- `redaction_reason`: Justification for redaction (or empty string)
- `valid_from`, `valid_to`, `recorded_at`: Bitemporal tracking fields

### C. OWNS Relationship
- `valid_from`: Start date of ownership tenure
- `valid_to`: End date of ownership tenure (empty string if current owner)
- `recorded_at`: Timestamp when relationship was recorded
- `status`: `'current'` | `'previous'`
- `source_id`: Source ID documenting the ownership assignment

---

## 2. Migration Execution (`scripts/migrate_v02_domain.py`)

Run the automated migration against any active graph:
```bash
python scripts/migrate_v02_domain.py --graph northwind_labs
```

### Forward Migration Steps
1. **Decision Nodes**: Backfills `recorded_at`, `confidence`, `review_status`, and `extracted_by`.
2. **Source Nodes**: Computes and sets SHA-256 `content_hash`, `origin_type`, `uri`, `visibility`, and `redacted=false`.
3. **OWNS Relationships**: Sets `valid_from`, `valid_to`, `recorded_at`, and `status`.

---

## 3. Rollback Plan

If rollback to v0.1 schema is required:
1. Properties added in v0.2 are non-destructive and backward-compatible with v0.1 queries.
2. To strip v0.2 properties:
```cypher
MATCH (d:Decision)
REMOVE d.recorded_at, d.confidence, d.review_status, d.extracted_by, d.extraction_run_id;

MATCH (s:Source)
REMOVE s.content_hash, s.origin_type, s.uri, s.visibility, s.redacted, s.redacted_at, s.redacted_by, s.redaction_reason;

MATCH ()-[r:OWNS]->()
REMOVE r.recorded_at, r.status;
```
3. Alternatively, restore from clean backup:
```bash
python scripts/backup_restore.py restore --graph northwind_labs --file data/backups/graph_backup.json
```
