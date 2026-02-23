import json

from .business_rules import legal_entity_name, stage_bucket_rule_text


def build_intent_prompt(question: str, stage_bucket: str = 'not_applied') -> str:
    stage_hint = stage_bucket_rule_text(stage_bucket)
    return (
        'You are an expert SQL planner. Convert the user question into a structured intent with these fields:\n'
        '- entity\n'
        '- metric (single string)\n'
        '- secondary_metric (optional string when user asks for two metrics)\n'
        '- aggregation\n'
        '- time_period\n'
        '- filters (list)\n'
        '- group_by (list)\n'
        '- order_by\n'
        '- limit\n'
        '- threshold\n'
        '- presentation\n\n'
        'Use this exact JSON shape (keys must match):\n'
        '{\n'
        '  "entity": null,\n'
        '  "metric": null,\n'
        '  "secondary_metric": null,\n'
        '  "aggregation": null,\n'
        '  "time_period": null,\n'
        '  "filters": [],\n'
        '  "group_by": [],\n'
        '  "order_by": null,\n'
        '  "limit": null,\n'
        '  "threshold": null,\n'
        '  "presentation": null\n'
        '}\n\n'
        'If the user asks for multiple metrics (e.g., revenue and margin), set "metric" to the primary one and'
        ' "secondary_metric" to the other.\n'
        'presentation semantics:\n'
        '- Use "text" for single KPI answers.\n'
        '- Use "table" for grouped results or multi-metric answers.\n'
        '- Use "bar" or "line" only when the user explicitly asks for a chart.\n\n'
        'UI-selected stage bucket rule (if selected):\n'
        f'- {stage_hint}\n'
        'If stage bucket is selected, include a filter object for deal_stage_name with operator in/not_in and exact values.\n\n'
        'Output ONLY valid JSON, nothing else.\n\n'
        f'User question: {question}\n'
    )


def build_intent_prompt_analytics(question: str, stage_bucket: str = 'not_applied') -> str:
    stage_hint = stage_bucket_rule_text(stage_bucket)
    return (
        'You are an expert CRO analytics planner. Convert the user question into structured intent.\n'
        'Include business-analysis semantics for target/budget/run-rate/scenario questions.\n'
        'Use this exact JSON shape:\n'
        '{\n'
        '  "entity": null,\n'
        '  "metric": null,\n'
        '  "secondary_metric": null,\n'
        '  "aggregation": null,\n'
        '  "time_period": null,\n'
        '  "filters": [],\n'
        '  "group_by": [],\n'
        '  "order_by": null,\n'
        '  "limit": null,\n'
        '  "threshold": null,\n'
        '  "presentation": null,\n'
        '  "comparison_type": null,\n'
        '  "goal_type": null,\n'
        '  "analysis_mode": null\n'
        '}\n'
        'UI-selected stage bucket rule (if selected):\n'
        f'- {stage_hint}\n'
        'If stage bucket is selected, include a filter object for deal_stage_name with operator in/not_in and exact values.\n'
        'If the user asks for multiple metrics (e.g., revenue and margin), set "metric" to the primary one and'
        ' "secondary_metric" to the other.\n'
        'presentation semantics:\n'
        '- Use "text" for single KPI answers.\n'
        '- Use "table" for grouped results or multi-metric answers.\n'
        '- Use "bar" or "line" only when the user explicitly asks for a chart.\n'
        'Output ONLY valid JSON.\n\n'
        f'Question: {question}\n'
    )


def build_router_prompt(question: str) -> str:
    return (
        'You are a routing classifier for a BI assistant.\n'
        'Choose exactly one route:\n'
        '- normal_intent: standard metric/time/filter/group questions\n'
        '- analytics_agent: executive questions about target/budget/run rate/coverage/risk/scenario/prioritization\n\n'
        'Return ONLY valid JSON:\n'
        '{\n'
        '  "route": "normal_intent" | "analytics_agent",\n'
        '  "reason": "short reason"\n'
        '}\n\n'
        f'Question: {question}\n'
    )


def build_sql_from_intent_prompt(
    intent: dict,
    schema_text: str,
    country_code: str,
    reporting_currency: str,
    stage_bucket: str,
    few_shot_examples: list[dict] | None = None,
) -> str:
    
    return (
        'You are a SQL generator. Return ONLY SQL (no markdown, no commentary).\n'
        'Dialect: Microsoft SQL Server (T-SQL). Do NOT use LIMIT.\n'
        'Rules: SELECT queries only. Use ONLY the provided table/column names.\n'
        'You MUST join dw.DimExchangeRate AS der  and bridgexchangerate and include this filter in WHERE:\n'
        f"- der.reporting_currency_code = '{reporting_currency}'\n"
        'You MUST join grp.DimLegalEntity AS dle and include these filters in WHERE:\n'
        f"- dle.legal_entity_name = '{legal_entity_name()}'\n"
        f"- dle.country_code = '{country_code}'\n"
        'You MUST join grp.DimDealStage AS ds and include this stage rule in WHERE:\n'
        f'- {stage_bucket_rule_text(stage_bucket)}\n'
        'For revenue or margin outputs, always return values in THOUSANDS (divide by 1000.0).\n'
        'Use aliases ending with _thousands for those fields.\n'
        'Return thousands as whole numbers (no decimal places).\n\n'
        'Schema and rules:\n'
        f'{schema_text}\n\n'
        """Date Schema
        date_key (int)
        calendar_date (date)
        calendar_year (smallint)
        calendar_month (smallint)
        calendar_quarter (smallint)
        start_of_month_date (date)
        end_of_month_date (date)
        DATE JOIN RULES (MANDATORY):

        - FactSale.close_date_key is INT and must join to dw.DimDate.date_key (INT).
        - NEVER compare date_key (INT) to calendar_date (DATE).
        - NEVER compare calendar_date to integer literals.
        - Join pattern must always be:

        JOIN dw.DimDate AS dd
            ON fs.close_date_key = dd.date_key

        - All time filtering must use dd.calendar_year, dd.calendar_month, dd.calendar_quarter.
        - Do NOT filter using dd.calendar_date unless comparing to DATE literal (e.g. '2024-01-01').
        - For month-to-date, use dd.calendar_month = current month AND dd.calendar_year = current year"""
        'Input intent JSON:\n'
        f'{json.dumps(intent, ensure_ascii=True)}\n\n'
        'Task: Generate a single T-SQL SELECT query that answers the intent.\n'
    )


def build_sql_from_analytics_prompt(
    question: str,
    intent: dict,
    schema_text: str,
    country_code: str,
    reporting_currency: str,
    stage_bucket: str,
    few_shot_examples: list[dict] | None = None,
) -> str:
    
    return (
        'You are an analytics SQL generator for executive revenue and budget questions.\n'
        'Return ONLY one T-SQL SELECT query (no markdown, commentary, or JSON).\n'
        'Dialect: Microsoft SQL Server (T-SQL). Do NOT use LIMIT.\n\n'
        f'This question is about: "{question}"\n\n'
        'DEFINITIONS:\n'
        '- actual_revenue_thousands: use grp.FactSale joined with grp.BridgeExchangeRate (revenue_fx) and dw.DimExchangeRate for reporting currency.\n'
        '- budget_revenue_thousands: use dw.FactBudget joined with grp.BridgeBudgetExchangeRate (revenue_fx) and dw.DimExchangeRate.\n\n'
        '- actual_margin_thousands: use grp.FactSale joined with grp.BridgeExchangeRate (margin_fx) and dw.DimExchangeRate for reporting currency.\n'
        '- budget_margin_thousands: use dw.FactBudget joined with grp.BridgeBudgetExchangeRate (margin_fx) and dw.DimExchangeRate.\n\n'
        'INCLUDE THESE FILTERS:\n'
        f"- der.reporting_currency_code = '{reporting_currency}'\n"
        f"- dle.legal_entity_name = '{legal_entity_name()}'\n"
        f"- dle.country_code = '{country_code}'\n"
        f'- Stage bucket filter specified by intent (e.g., {stage_bucket_rule_text(stage_bucket)})\n\n'
        'TIME FILTERS:\n'
        "- actual month-to-date = close_date between first day of current month and today's date.\n"
        '- budget for the full current month.\n\n'
        'REQUIREMENTS:\n'
        '1) Use CTEs - one for actual MTD and one for budget full month.\n'
        '2) Do NOT calculate run-rate or risk status in SQL - only return the two raw numbers.\n'
        '3) Divide revenue values by 1000.0 and remove decimals.\n'
        '4) Use only SELECT/WITH and valid T-SQL constructs.\n\n'
        'Allowed tables:\n'
        'grp.FactSale, grp.BridgeExchangeRate, dw.DimExchangeRate, grp.DimLegalEntity, dw.DimDate, grp.DimDealStage,\n'
        'dw.FactBudget, grp.BridgeBudgetExchangeRate\n\n'
        'Schema and rules:\n'
        """Date Schema
        date_key (int)
        calendar_date (date)
        calendar_year (smallint)
        calendar_month (smallint)
        calendar_quarter (smallint)
        start_of_month_date (date)
        end_of_month_date (date)
        DATE JOIN RULES (MANDATORY):

        - FactSale.close_date_key is INT and must join to dw.DimDate.date_key (INT).
        - NEVER compare date_key (INT) to calendar_date (DATE).
        - NEVER compare calendar_date to integer literals.
        - Join pattern must always be:

        JOIN dw.DimDate AS dd
            ON fs.close_date_key = dd.date_key

        - All time filtering must use dd.calendar_year, dd.calendar_month, dd.calendar_quarter.
        - Do NOT filter using dd.calendar_date unless comparing to DATE literal (e.g. '2024-01-01').
        - For month-to-date, use dd.calendar_month = current month AND dd.calendar_year = current year"""""
        f'{schema_text}\n\n'
        'Intent JSON:\n'
        f'{json.dumps(intent, ensure_ascii=True)}\n\n'
        'Use BridgeExchangeRate and BudgetBridgeExchangeRate for currency conversion. Join with DimExchangeRate for reporting currency filter.\n\n'
        'Generate ONLY the SQL that returns these two numeric columns.\n'
    )


def build_narrative_prompt(question: str, columns: list[str], rows: list[list], reporting_currency: str = 'GBP') -> str:
    preview_rows = rows[:20]
    symbol_desc = 'pound symbol (£)' if reporting_currency == 'GBP' else 'Canadian dollar symbol (C$)'
    symbol_example = '£12k' if reporting_currency == 'GBP' else 'C$12k'
    return (
        'You are a data analyst. Answer the user\'s question in natural language '
        'based only on the provided query results. If the number of rows is 0, say No results found.'
        'Otherwise summarize the results.'
        f'If values are revenue/margin in thousands {reporting_currency}, format with '
        f'{symbol_desc} and k '
        f'(example: {symbol_example}, no decimals).\n\n'
        f'Question: {question}\n'
        f'Columns (JSON): {json.dumps(columns)}\n'
        f'Rows (JSON): {json.dumps(preview_rows)}\n'
    )


def build_sql_validator_prompt(
    question: str,
    intent: dict,
    proposed_sql: str,
    country_code: str,
    reporting_currency: str,
    stage_bucket: str,
    few_shot_examples: list[dict] | None = None,
) -> str:
    examples_block = ''
    if few_shot_examples:
        lines = ['Reference examples (validated):']
        for idx, ex in enumerate(few_shot_examples, start=1):
            lines.append(f'Example {idx} question: {ex.get("question", "")}')
            lines.append('Example SQL:')
            lines.append(str(ex.get('sql_text', '')).strip())
            lines.append('')
        examples_block = '\n'.join(lines).strip() + '\n\n'
    return (
        'You are a SQL validator and fixer.\n'
        'Task: validate the proposed SQL against question + intent + schema + hard constraints.\n'
        'Return ONLY corrected T-SQL SELECT statement (no markdown, no commentary).\n'
        'If SQL is already correct, return the same SQL.\n'
        'Hard constraints:\n'
        '- Must be T-SQL (no LIMIT).\n'
        '- SELECT/WITH only.\n'
        '- Must include dw.DimExchangeRate join/filter with reporting currency.\n'
        '- Must include grp.DimLegalEntity join and filters.\n'
        f"- reporting currency filter: der.reporting_currency_code = '{reporting_currency}'\n"
        f"- legal entity filter: dle.legal_entity_name = '{legal_entity_name()}'\n"
        f"- country filter: dle.country_code = '{country_code}'\n"
        f"- stage bucket rule: {stage_bucket_rule_text(stage_bucket)}\n\n"
        f'Question: {question}\n'
        f'Intent JSON: {json.dumps(intent, ensure_ascii=True)}\n\n'
        f'{examples_block}'
        'Use intent fields as the source of truth for metric/time/filters/grouping.\n\n'
        'Proposed SQL:\n'
        f'{proposed_sql}\n\n'
        'Return ONLY corrected SQL.\n'
    )


def build_analytics_summary_prompt(
    question: str,
    engine_name: str,
    kpis: dict,
    tables: dict,
    reporting_currency: str = 'GBP',
) -> str:
    symbol = '£' if reporting_currency == 'GBP' else 'C$'
    return (
        'You are a CRO analytics assistant. Answer using ONLY provided analytics outputs.\n'
        'Be concise, factual, and executive-focused.\n'
        'If data is missing, state that clearly.\n'
        f'Currency symbol: {symbol}. Thousands format: {symbol}123K (no decimals).\n\n'
        f'Question: {question}\n'
        f'Engine: {engine_name}\n'
        f'KPIs (JSON): {json.dumps(kpis)}\n'
        f'Tables (JSON): {json.dumps(tables)}\n\n'
        'Output format:\n'
        '1) Direct answer (1-2 lines)\n'
        '2) Key evidence (up to 3 bullets)\n'
        '3) Risk/Opportunity (1 line)\n'
        '4) Recommended action (1 line)\n'
    )
