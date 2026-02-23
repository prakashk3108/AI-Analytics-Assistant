from .business_rules import get_business_rules, legal_entity_name
from .db import get_schema_details_text, get_schema_text
from .example_store import find_similar_examples
from .gemini_client import call_gemini
from .prompt_builder import (
    build_narrative_prompt,
    build_sql_from_analytics_prompt,
    build_sql_from_intent_prompt,
    build_sql_validator_prompt,
)


def validate_sql(sql: str) -> str:
    cleaned = sql.strip()
    if '```' in cleaned:
        pieces = cleaned.split('```', 2)
        cleaned = pieces[1] if len(pieces) > 1 else cleaned
        cleaned = cleaned.replace('sql', '', 1).strip()
    if cleaned == '-- CANNOT_ANSWER':
        return cleaned
    lowered = cleaned.lower()
    start_idx = lowered.find('select')
    with_idx = lowered.find('with')
    candidates = [idx for idx in (start_idx, with_idx) if idx != -1]
    if not candidates:
        preview = cleaned[:200].replace('\n', ' ')
        raise RuntimeError(f'LLM did not return a SELECT query. Got: {preview!r}')
    cleaned = cleaned[min(candidates) :]
    lowered = cleaned.lower().rstrip(';')
    forbidden = ['insert', 'update', 'delete', 'drop', 'alter', 'pragma', 'attach', 'create', 'limit']
    if any(token in lowered for token in forbidden):
        raise RuntimeError('Unsafe SQL detected')
    return cleaned.strip().rstrip(';')


def extract_sql_snippet(text: str) -> str:
    cleaned = (text or '').strip()
    if '```' in cleaned:
        pieces = cleaned.split('```')
        if len(pieces) >= 3:
            cleaned = pieces[1].strip()
            if cleaned.lower().startswith('sql'):
                cleaned = cleaned[3:].strip()
    lowered = cleaned.lower()
    select_idx = lowered.find('select')
    with_idx = lowered.find('with')
    candidates = [idx for idx in (select_idx, with_idx) if idx != -1]
    if not candidates:
        return ''
    return cleaned[min(candidates) :].strip()


def enforce_sql_requirements(
    sql_text: str,
    country_code: str = 'GBR',
    reporting_currency: str = 'GBP',
    stage_bucket: str = 'pipeline',
) -> list[str]:
    if (sql_text or '').strip() == '-- CANNOT_ANSWER':
        return []
    sql_lower = sql_text.lower()
    sql_norm = (
        sql_lower.replace('[', '')
        .replace(']', '')
        .replace('"', '')
        .replace("'", '')
        .replace('\n', ' ')
        .replace('\t', ' ')
    )
    violations: list[str] = []

    required = [
        'dw.dimexchangerate',
        'reporting_currency_code',
        reporting_currency.lower(),
        'grp.dimlegalentity',
        'dle',
        'dle.legal_entity_name',
        legal_entity_name().lower(),
        'dle.country_code',
        country_code.lower(),
    ]
    missing = [s for s in required if s not in sql_norm]
    if missing:
        violations.append(
            'Missing required constraints/joins: '
            + ', '.join(missing)
            + '. SQL must include exchange rate join+reporting currency filter and legal entity join+HubSpot/region filter.'
        )

    if ' limit ' in f' {sql_norm} ':
        violations.append('T-SQL does not support LIMIT. Use TOP or OFFSET/FETCH.')

    stage_rule = get_business_rules().get('stage_buckets', {}).get(stage_bucket, {})
    stage_mode = str(stage_rule.get('mode', 'in')).lower()
    stage_values = [str(v).lower() for v in stage_rule.get('values', [])]
    if stage_mode == 'none':
        return violations

    required_stage = ['grp.dimdealstage', 'deal_stage_name']
    missing_stage_join = [s for s in required_stage if s not in sql_norm]
    if missing_stage_join:
        violations.append('Missing required stage join/filter context: ' + ', '.join(missing_stage_join))

    if stage_values:
        if stage_mode == 'not_in' and ' not in ' not in f' {sql_norm} ':
            violations.append('Stage rule must use NOT IN for the selected stage bucket.')
        if stage_mode == 'in' and ' in ' not in f' {sql_norm} ':
            violations.append('Stage rule must use IN for the selected stage bucket.')
        missing_values = [v for v in stage_values if v not in sql_norm]
        if missing_values:
            violations.append('Missing required stage values for selected stage bucket: ' + ', '.join(missing_values))

    return violations


def enforce_analytics_requirements(question: str, sql_text: str) -> list[str]:
    if (sql_text or '').strip() == '-- CANNOT_ANSWER':
        return []
    q = (question or '').lower()
    s = (sql_text or '').lower()
    needs_budget = any(k in q for k in ['target', 'budget', 'on track', 'run rate', 'gap', 'ahead', 'behind'])
    violations = []
    if needs_budget and ('factbudget' not in s and 'budget' not in s):
        violations.append(
            'Analytics question appears target/budget based. SQL must include budget/target source (for example dw.FactBudget).'
        )
    return violations


def validate_and_fix_sql_with_llm(
    question: str,
    intent: dict,
    sql_text: str,
    country_code: str,
    reporting_currency: str,
    stage_bucket: str,
    few_shot_examples: list[dict] | None = None,
) -> tuple[str, str]:
    prompt = build_sql_validator_prompt(
        question=question,
        intent=intent,
        proposed_sql=sql_text,
        country_code=country_code,
        reporting_currency=reporting_currency,
        stage_bucket=stage_bucket,
        few_shot_examples=few_shot_examples,
    )
    raw = call_gemini(prompt)
    if not raw:
        return sql_text, ''
    candidate = extract_sql_snippet(raw) or raw
    try:
        fixed = validate_sql(candidate)
        return fixed, raw
    except Exception:
        return sql_text, raw


def generate_sql_from_intent(
    intent: dict,
    country_code: str,
    reporting_currency: str,
    stage_bucket: str,
    question: str = '',
) -> tuple[str, str, str, dict]:
    schema_text = get_schema_details_text() or get_schema_text()
    examples = find_similar_examples(question, top_k=3) if question else []
    prompt_used = build_sql_from_intent_prompt(
        intent,
        schema_text,
        country_code,
        reporting_currency,
        stage_bucket,
        few_shot_examples=examples,
    )

    sql_text = None
    llm_raw = None
    generator_sql = ''
    validated_sql = ''
    last_violations: list[str] = []
    for _ in range(2):
        llm_raw = call_gemini(prompt_used)
        if not llm_raw:
            raise RuntimeError('LLM returned no SQL.')
        sql_candidate = extract_sql_snippet(llm_raw) or llm_raw
        generator_sql = validate_sql(sql_candidate)
        sql_text = generator_sql
        sql_text, validator_raw = validate_and_fix_sql_with_llm(
            question=question,
            intent=intent,
            sql_text=sql_text,
            country_code=country_code,
            reporting_currency=reporting_currency,
            stage_bucket=stage_bucket,
            few_shot_examples=examples,
        )
        if validator_raw:
            llm_raw = (llm_raw or '') + '\n\n[sql_validator]\n' + validator_raw
        validated_sql = sql_text
        violations = enforce_sql_requirements(
            sql_text,
            country_code=country_code,
            reporting_currency=reporting_currency,
            stage_bucket=stage_bucket,
        )
        if not violations:
            return (
                sql_text,
                llm_raw or '',
                prompt_used,
                {
                    'generator_sql': generator_sql,
                    'validated_sql': validated_sql or sql_text,
                    'similar_examples': examples,
                },
            )
        last_violations = violations
        prompt_used = (
            prompt_used
            + '\nYour previous SQL was INVALID.\n'
            + 'Fix these issues and return ONLY corrected SQL:\n- '
            + '\n- '.join(violations)
            + '\n\nPrevious SQL:\n'
            + sql_text
            + '\n'
        )

    raise RuntimeError('SQL did not meet hard requirements:\n' + '\n'.join(last_violations))


def generate_sql_for_route(
    route: str,
    question: str,
    intent: dict,
    country_code: str,
    reporting_currency: str,
    stage_bucket: str,
) -> tuple[str, str, str, str, dict]:
    if route != 'analytics_agent':
        sql_text, llm_raw, prompt, meta = generate_sql_from_intent(
            intent, country_code, reporting_currency, stage_bucket, question
        )
        return sql_text, llm_raw, prompt, 'normal_intent', meta

    schema_text = get_schema_details_text() or get_schema_text()
    examples = find_similar_examples(question, top_k=3) if question else []
    prompt_used = build_sql_from_analytics_prompt(
        question,
        intent,
        schema_text,
        country_code,
        reporting_currency,
        stage_bucket,
        few_shot_examples=examples,
    )

    sql_text = None
    llm_raw = None
    generator_sql = ''
    validated_sql = ''
    for _ in range(2):
        llm_raw = call_gemini(prompt_used)
        if not llm_raw:
            raise RuntimeError('LLM returned no SQL.')
        sql_candidate = extract_sql_snippet(llm_raw) or llm_raw
        generator_sql = validate_sql(sql_candidate)
        sql_text = generator_sql
        sql_text, validator_raw = validate_and_fix_sql_with_llm(
            question=question,
            intent=intent,
            sql_text=sql_text,
            country_code=country_code,
            reporting_currency=reporting_currency,
            stage_bucket=stage_bucket,
            few_shot_examples=examples,
        )
        if validator_raw:
            llm_raw = (llm_raw or '') + '\n\n[sql_validator]\n' + validator_raw
        validated_sql = sql_text
        violations = enforce_sql_requirements(
            sql_text,
            country_code=country_code,
            reporting_currency=reporting_currency,
            stage_bucket=stage_bucket,
        )
        violations.extend(enforce_analytics_requirements(question, sql_text))
        if not violations:
            return (
                sql_text,
                llm_raw or '',
                prompt_used,
                'analytics_agent',
                {
                    'generator_sql': generator_sql,
                    'validated_sql': validated_sql or sql_text,
                    'similar_examples': examples,
                },
            )
        prompt_used = (
            prompt_used
            + '\nPrevious SQL violated requirements. Return ONLY corrected SQL.\n- '
            + '\n- '.join(violations)
            + '\n\nPrevious SQL:\n'
            + sql_text
            + '\n'
        )

    fallback_sql, fallback_raw, fallback_prompt, fallback_meta = generate_sql_from_intent(
        intent, country_code, reporting_currency, stage_bucket, question
    )
    return (
        fallback_sql,
        (llm_raw or '') + '\n\n[analytics_fallback]\n' + (fallback_raw or ''),
        prompt_used + '\n\n[Fallback to normal_intent path]\n' + fallback_prompt,
        'analytics_agent_fallback_to_normal',
        fallback_meta,
    )


def call_gemini_nl(question: str, columns: list[str], rows: list[list], reporting_currency: str = 'GBP') -> str | None:
    payload = {
        'contents': [{'parts': [{'text': build_narrative_prompt(question, columns, rows, reporting_currency)}]}],
        'generationConfig': {'temperature': 0.2},
    }
    from .gemini_client import gemini_request

    data = gemini_request(payload, timeout_s=25, max_retries=2)
    candidates = data.get('candidates') or []
    if not candidates:
        return None
    parts = candidates[0].get('content', {}).get('parts') or []
    if not parts:
        return None
    return parts[0].get('text')
