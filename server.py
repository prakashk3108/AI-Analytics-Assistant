import os
import sys
import traceback
import threading
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.business_rules import (
    country_code_for_region,
    legal_entity_name,
    normalize_region,
    normalize_reporting_currency,
    normalize_stage_bucket,
    stage_bucket_predicate,
)
from core.config import BASE_DIR, load_env, log_error
from core.db import get_connection, list_tables
from core.example_store import add_example, delete_example, find_similar_examples, init_examples_db, list_examples
from core.intent_router import apply_stage_bucket_to_intent, plan_intent, route_question
from core.serializers import format_rows, json_rows
from core.sql_engine import call_gemini_nl, generate_sql_for_route

load_env()
init_examples_db()

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")
PAGES_DIR = os.path.join(BASE_DIR, "pages")
HTML_PAGES = {
    "index.html",
    "full_ui.html",
    "intent.html",
    "prompt_to_sql.html",
    "sql_from_intent.html",
    "examples.html",
}

# Global request gate: only one long-running query at a time.
REQUEST_SEM = threading.Semaphore(1)


@app.after_request
def disable_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "sqlfromllm"})


@app.get("/")
def root():
    return send_from_directory(PAGES_DIR, "full_ui.html")


@app.get("/<path:page>")
def serve_page_or_asset(page: str):
    if page in HTML_PAGES:
        return send_from_directory(PAGES_DIR, page)
    return send_from_directory(BASE_DIR, page)


@app.get("/api/examples/similar")
def api_examples_similar():
    try:
        q = (request.args.get("q") or "").strip()
        if not q:
            return jsonify({"error": "Missing q"}), 400
        return jsonify({"examples": find_similar_examples(q)})
    except Exception:
        trace = traceback.format_exc()
        log_error(trace)
        return jsonify({"error": "Failed to search examples", "detail": trace}), 500


@app.get("/api/examples")
def api_examples_list():
    try:
        return jsonify({"examples": list_examples()})
    except Exception:
        trace = traceback.format_exc()
        log_error(trace)
        return jsonify({"error": "Failed to list examples", "detail": trace}), 500


@app.post("/api/examples")
def api_examples_add():
    try:
        payload = request.get_json(force=True, silent=True) or {}
        question = str(payload.get("question") or "").strip()
        sql_text = str(payload.get("sql") or payload.get("sql_text") or "").strip()
        tags = payload.get("tags") or []
        notes = str(payload.get("notes") or "").strip()
        if not question or not sql_text:
            return jsonify({"error": "question and sql are required"}), 400
        row_id = add_example(question, sql_text, tags=tags, notes=notes)
        return jsonify({"id": row_id}), 201
    except Exception as exc:
        trace = traceback.format_exc()
        log_error(trace)
        return jsonify({"error": str(exc), "detail": trace}), 500


@app.delete("/api/examples/<int:example_id>")
def api_examples_delete(example_id: int):
    try:
        deleted = delete_example(example_id)
        if not deleted:
            return jsonify({"error": "Example not found"}), 404
        return jsonify({"ok": True, "id": example_id})
    except Exception as exc:
        trace = traceback.format_exc()
        log_error(trace)
        return jsonify({"error": str(exc), "detail": trace}), 500


@app.get("/api/tables")
def api_tables():
    try:
        return jsonify({"tables": list_tables()})
    except Exception:
        trace = traceback.format_exc()
        log_error(trace)
        return jsonify({"error": "Failed to list tables", "detail": trace}), 500


@app.get("/api/kpi_strip")
def api_kpi_strip():
    try:
        region = normalize_region(request.args.get("region"))
        country_code = country_code_for_region(region)
        reporting_currency = normalize_reporting_currency(request.args.get("reporting_currency"))
        stage_bucket = normalize_stage_bucket(request.args.get("stage_bucket"))

        stage_sql = stage_bucket_predicate(stage_bucket, alias="ds")
        pipeline_sql = stage_bucket_predicate("pipeline", alias="ds")
        entity_name = legal_entity_name().replace("'", "''")

        sql_text = f"""
WITH current_quarter AS (
  SELECT
    MIN(dd.calendar_date) AS q_start,
    MAX(dd.calendar_date) AS q_end,
    MAX(dd.calendar_year) AS q_year,
    MAX(dd.calendar_quarter) AS q_quarter
  FROM dw.DimDate dd
  WHERE dd.calendar_year = YEAR(GETDATE())
    AND dd.calendar_quarter = DATEPART(QUARTER, GETDATE())
),
actuals AS (
  SELECT
    SUM(ber.revenue_fx) / 1000.0 AS revenue_k,
    SUM(ber.margin_fx) / 1000.0 AS margin_k
  FROM grp.FactSale fs
  JOIN grp.BridgeExchangeRate ber ON fs.sale_key = ber.sale_key
  JOIN dw.DimExchangeRate der ON ber.exchange_rate_key = der.exchange_rate_key
  JOIN grp.DimLegalEntity dle ON fs.legal_entity_id = dle.legal_entity_id
  JOIN dw.DimDate dd ON fs.close_date_key = dd.date_key
  JOIN grp.DimDealStage ds ON fs.deal_stage_key = ds.deal_stage_key
  CROSS JOIN current_quarter cq
  WHERE der.reporting_currency_code = ?
    AND dle.legal_entity_name = ?
    AND dle.country_code = ?
    AND dd.calendar_date >= cq.q_start
    AND dd.calendar_date <= cq.q_end
    AND ({stage_sql})
),
budget AS (
  SELECT
    SUM(bber.revenue_fx) / 1000.0 AS budget_revenue_k
  FROM dw.FactBudget fb
  JOIN grp.BridgeBudgetExchangeRate bber ON fb.budget_key = bber.budget_key
  JOIN dw.DimExchangeRate der ON bber.exchange_rate_key = der.exchange_rate_key
  JOIN grp.DimLegalEntity dle ON fb.legal_entity_id = dle.legal_entity_id
  JOIN dw.DimDate dd ON fb.month_end_date_key = dd.date_key
  CROSS JOIN current_quarter cq
  WHERE der.reporting_currency_code = ?
    AND dle.legal_entity_name = ?
    AND dle.country_code = ?
    AND dd.calendar_year = cq.q_year
    AND dd.calendar_quarter = cq.q_quarter
),
pipeline AS (
  SELECT
    SUM(ber.revenue_fx) / 1000.0 AS pipeline_k
  FROM grp.FactSale fs
  JOIN grp.BridgeExchangeRate ber ON fs.sale_key = ber.sale_key
  JOIN dw.DimExchangeRate der ON ber.exchange_rate_key = der.exchange_rate_key
  JOIN grp.DimLegalEntity dle ON fs.legal_entity_id = dle.legal_entity_id
  JOIN dw.DimDate dd ON fs.close_date_key = dd.date_key
  JOIN grp.DimDealStage ds ON fs.deal_stage_key = ds.deal_stage_key
  CROSS JOIN current_quarter cq
  WHERE der.reporting_currency_code = ?
    AND dle.legal_entity_name = ?
    AND dle.country_code = ?
    AND dd.calendar_date >= cq.q_start
    AND dd.calendar_date <= cq.q_end
    AND ({pipeline_sql})
)
SELECT
  a.revenue_k,
  a.margin_k,
  b.budget_revenue_k,
  (b.budget_revenue_k - a.revenue_k) AS gap_k,
  CASE WHEN b.budget_revenue_k = 0 THEN NULL ELSE p.pipeline_k / b.budget_revenue_k END AS coverage_ratio
FROM actuals a
CROSS JOIN budget b
CROSS JOIN pipeline p;
"""

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            sql_text,
            (
                reporting_currency,
                entity_name,
                country_code,
                reporting_currency,
                entity_name,
                country_code,
                reporting_currency,
                entity_name,
                country_code,
            ),
        )
        row = cursor.fetchone()
        conn.close()

        def as_float(value):
            if value is None:
                return None
            try:
                return float(value)
            except Exception:
                return None

        revenue_k = as_float(row[0]) if row else None
        margin_k = as_float(row[1]) if row else None
        budget_k = as_float(row[2]) if row else None
        gap_k = as_float(row[3]) if row else None
        coverage_ratio = as_float(row[4]) if row else None
        now = datetime.utcnow()
        quarter_label = f"Q{((now.month - 1) // 3) + 1} {now.year}"

        return jsonify(
            {
                "quarter": quarter_label,
                "region": region,
                "reporting_currency": reporting_currency,
                "stage_bucket": stage_bucket,
                "kpis": {
                    "revenue_k": revenue_k,
                    "margin_k": margin_k,
                    "budget_revenue_k": budget_k,
                    "gap_k": gap_k,
                    "coverage_ratio": coverage_ratio,
                },
            }
        )
    except Exception as exc:
        trace = traceback.format_exc()
        log_error(trace)
        return jsonify({"error": str(exc), "detail": trace}), 500


@app.post("/api/intent")
def api_intent():
    try:
        payload = request.get_json(force=True, silent=True) or {}
        ui = payload.get("ui") if isinstance(payload.get("ui"), dict) else {}
        question = (payload.get("query") or "").strip()
        if not question:
            return jsonify({"error": "Missing query"}), 400
        stage_bucket = normalize_stage_bucket(payload.get("stage_bucket") or ui.get("stage_bucket"))
        router = route_question(question)
        route = router.get("route", "normal_intent")
        intent = plan_intent(question, route=route, stage_bucket=stage_bucket)
        return jsonify(
            {
                "route": route,
                "route_reason": router.get("reason"),
                "route_raw": router.get("_raw"),
                "intent": intent,
                "raw": intent.get("_raw"),
            }
        )
    except Exception as exc:
        trace = traceback.format_exc()
        log_error(trace)
        return jsonify({"error": str(exc), "detail": trace}), 500


@app.post("/api/sql_from_intent")
def api_sql_from_intent():
    try:
        with REQUEST_SEM:
            payload = request.get_json(force=True, silent=True) or {}
            ui = payload.get("ui") if isinstance(payload.get("ui"), dict) else {}
            intent = payload.get("intent")
            if not isinstance(intent, dict):
                return jsonify({"error": "Missing intent object"}), 400

            region = normalize_region(payload.get("region") or ui.get("region"))
            country_code = country_code_for_region(region)
            reporting_currency = normalize_reporting_currency(
                payload.get("reporting_currency") or ui.get("reporting_currency")
            )
            stage_bucket = normalize_stage_bucket(payload.get("stage_bucket") or ui.get("stage_bucket"))
            route = str(payload.get("route") or intent.get("_route") or "normal_intent").lower()
            preview_sql_only = bool(payload.get("preview_sql_only"))
            intent = apply_stage_bucket_to_intent(intent, stage_bucket)

            sql_text, llm_raw, prompt_used, route_used, sql_meta = generate_sql_for_route(
                route,
                payload.get("question") or "",
                intent,
                country_code,
                reporting_currency,
                stage_bucket,
            )

            if preview_sql_only:
                return jsonify(
                    {
                        "sql": sql_text,
                        "llm_raw": llm_raw,
                        "prompt": prompt_used,
                        "columns": [],
                        "rows": [],
                        "answer": "SQL preview only. Query not executed.",
                        "narrative": None,
                        "route_used": route_used,
                        "region": region,
                        "country_code": country_code,
                        "stage_bucket": stage_bucket,
                        "reporting_currency": reporting_currency,
                        "preview_sql_only": True,
                        "generator_sql": (sql_meta or {}).get("generator_sql"),
                        "validated_sql": (sql_meta or {}).get("validated_sql"),
                        "similar_examples": (sql_meta or {}).get("similar_examples", []),
                    }
                )

            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(sql_text)
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                conn.close()
            except Exception as exec_exc:
                trace = traceback.format_exc()
                log_error(trace)
                return (
                    jsonify(
                        {
                            "error": str(exec_exc),
                            "detail": trace,
                            "sql": sql_text,
                            "llm_raw": llm_raw,
                            "prompt": prompt_used,
                            "route_used": route_used,
                            "generator_sql": (sql_meta or {}).get("generator_sql"),
                            "validated_sql": (sql_meta or {}).get("validated_sql"),
                            "similar_examples": (sql_meta or {}).get("similar_examples", []),
                        }
                    ),
                    500,
                )

            rows_json = json_rows(rows)
            include_narrative = bool(payload.get("include_narrative"))
            narrative = None
            if include_narrative:
                narrative = call_gemini_nl(
                    payload.get("question") or "Answer the intent.",
                    columns,
                    rows_json,
                    reporting_currency,
                )

            return jsonify(
                {
                    "sql": sql_text,
                    "llm_raw": llm_raw,
                    "prompt": prompt_used,
                    "columns": columns,
                    "rows": rows_json,
                    "answer": format_rows(rows, columns),
                    "narrative": narrative,
                    "route_used": route_used,
                    "region": region,
                    "country_code": country_code,
                    "stage_bucket": stage_bucket,
                    "reporting_currency": reporting_currency,
                    "generator_sql": (sql_meta or {}).get("generator_sql"),
                    "validated_sql": (sql_meta or {}).get("validated_sql"),
                    "similar_examples": (sql_meta or {}).get("similar_examples", []),
                }
            )
    except Exception as exc:
        trace = traceback.format_exc()
        log_error(trace)
        return jsonify({"error": str(exc), "detail": trace}), 500


@app.post("/api/sql")
def api_sql():
    try:
        with REQUEST_SEM:
            payload = request.get_json(force=True, silent=True) or {}
            ui = payload.get("ui") if isinstance(payload.get("ui"), dict) else {}
            question = (payload.get("query") or "").strip()
            if not question:
                return jsonify({"error": "Missing query"}), 400

            router = route_question(question)
            route = router.get("route", "normal_intent")
            stage_bucket = normalize_stage_bucket(payload.get("stage_bucket") or ui.get("stage_bucket"))
            intent = plan_intent(question, route=route, stage_bucket=stage_bucket)

            region = normalize_region(payload.get("region") or ui.get("region"))
            country_code = country_code_for_region(region)
            reporting_currency = normalize_reporting_currency(
                payload.get("reporting_currency") or ui.get("reporting_currency")
            )

            sql_text, llm_raw, prompt_used, route_used, sql_meta = generate_sql_for_route(
                route,
                question,
                intent,
                country_code,
                reporting_currency,
                stage_bucket,
            )

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(sql_text)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            conn.close()
            rows_json = json_rows(rows)

            return jsonify(
                {
                    "sql": sql_text,
                    "llm_raw": llm_raw,
                    "columns": columns,
                    "rows": rows_json,
                    "answer": format_rows(rows, columns),
                    "prompt": prompt_used,
                    "route_used": route_used,
                    "intent": intent,
                    "generator_sql": (sql_meta or {}).get("generator_sql"),
                    "validated_sql": (sql_meta or {}).get("validated_sql"),
                    "similar_examples": (sql_meta or {}).get("similar_examples", []),
                }
            )
    except Exception as exc:
        trace = traceback.format_exc()
        log_error(trace)
        return jsonify({"error": str(exc), "detail": trace}), 500


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/<path:path>")
def static_files(path: str):
    return send_from_directory(BASE_DIR, path)


def run_server():
    port = int(os.environ.get("PORT", "8000"))
    print(f"Flask server running at http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, threaded=True)


if __name__ == "__main__":
    run_server()
