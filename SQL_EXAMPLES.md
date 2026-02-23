# SQL Examples Memory

This project now supports a local DB table of sample questions and verified SQL.

## Storage
- File: `sql_examples.db`
- Table: `sql_examples`
  - `id`
  - `question`
  - `sql_text`
  - `tags` (JSON array)
  - `notes`
  - `created_at`

## APIs

### Add one example
`POST /api/examples`

Body:
```json
{
  "question": "revenue last month by revenue type",
  "sql": "SELECT ...",
  "tags": ["revenue", "monthly"],
  "notes": "validated in UAT"
}
```

### List examples
`GET /api/examples`

### Find similar examples
`GET /api/examples/similar?q=revenue%20last%20month`

## Runtime behavior
- On every SQL generation call, the system finds top similar stored examples.
- Those examples are injected into the SQL prompt as few-shot guidance.
- This applies to both:
  - `normal_intent` path
  - `analytics_agent` path

## Similarity method
- Primary: Gemini embeddings (`text-embedding-004`) + cosine similarity.
- Fallback: lexical similarity (SequenceMatcher + token Jaccard) if embeddings fail.
- Existing rows are lazily backfilled with embeddings when searched.
