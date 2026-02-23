# SQLfromLLM Report (What We Built + Flow)

This document summarizes the current build, key features, and execution flow.

## What This Project Does
- Web UI for asking revenue/margin/budget questions.
- LLM plans intent → generates SQL → validates → runs against Fabric DW.
- Results shown as text by default; tables/charts only on explicit request.
- Supports stage bucket filters, region, and reporting currency.
- Example store for approved questions/SQL.

## Current UI Pages
All HTML pages are in `pages/` and served by Flask.
- `pages/full_ui.html` (main CRO Copilot)
- `pages/index.html` (simple UI)
- `pages/intent.html`
- `pages/sql_from_intent.html`
- `pages/prompt_to_sql.html`
- `pages/examples.html`

## Endpoints (Server)
`server.py` (Flask) serves:
- `GET /` → `pages/full_ui.html`
- `GET /<page>.html` → from `pages/`
- `GET /api/health`
- `POST /api/intent`
- `POST /api/sql_from_intent`
- `POST /api/sql` (legacy / direct)
- `GET /api/tables`
- `GET /api/examples`, `POST /api/examples`, `DELETE /api/examples/<id>`
- `GET /api/examples/similar`

## Core Flow (User Question → Answer)
1. **User asks question** in `full_ui.html`.
2. **Stage scope prompt** appears in chat (if enabled).
3. **Intent step** (`/api/intent`):
   - `core/intent_router.py` routes to `normal_intent` or `analytics_agent`.
   - `core/prompt_builder.py` builds the intent prompt.
   - Output JSON includes metric/time/group_by/presentation/etc.
4. **SQL generation** (`/api/sql_from_intent`):
   - `core/sql_engine.py` builds SQL prompt using schema + business rules.
   - Gemini generates SQL.
   - SQL validation/repair applied (hard rules + intent rules).
5. **DW execution** (`core/db.py`):
   - Query executed against Fabric SQL endpoint.
6. **Response rendering**:
   - Default: text summary.
   - If question/intent asks for table or chart: table/bar/line.
   - Charts rendered in chat; tables rendered in chat or details.

## Rendering Rules (UI)
Default output is **text**.
Only switch when explicitly requested:
- “table” → table
- “bar chart” → bar chart
- “line chart” / “trend” → line chart

## Intent Schema (Current)
Intent includes:
- `entity`, `metric`, `secondary_metric`
- `aggregation`, `time_period`
- `filters` (list)
- `group_by`, `order_by`, `limit`
- `threshold`, `presentation`
- analytics fields (optional): `comparison_type`, `goal_type`, `analysis_mode`

Multiple metrics rule:
- Use `metric` + `secondary_metric` (do NOT return array).

## Business Rules & Constraints
Prompts enforce:
- Join to `dw.DimExchangeRate` for reporting currency.
- Join to `grp.DimLegalEntity` for legal entity + country filters.
- Use `dw.DimDate` for time filters.
- Stage bucket rules via `grp.DimDealStage`.
- Revenue/margin in thousands (divide by 1000.0).

## Example Store (Similarity)
Approved Q→SQL pairs stored and retrieved for similar queries.
- Files: `core/example_store.py`, `SQL_EXAMPLES.md` (reference)

## Visual/UI Changes
- CRO Copilot theme.
- Stage scope in-chat prompt.
- Region + Currency selectors.
- Question Library (grouped capability list).
- Charts: vertical grouped bars with y-axis, line chart with legend.
- Narrative text cleaned to new lines per record.

## How To Run
From project root:
```
python server.py
```
Then open:
```
http://localhost:8030/
```

## Notes / Known Limits
- Charts are limited to two numeric series.
- Bar charts show max 8 categories.
- Default output is text unless explicitly requested.
