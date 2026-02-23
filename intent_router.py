import json

from .business_rules import get_business_rules, normalize_stage_bucket
from .gemini_client import call_gemini
from .prompt_builder import build_intent_prompt, build_intent_prompt_analytics, build_router_prompt


def extract_json_object(text: str) -> str | None:
    if not text:
        return None
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def route_question(question: str) -> dict:
    q = (question or '').lower()
    keyword_hits = [
        'on track',
        'target',
        'budget',
        'run rate',
        'coverage',
        'scenario',
        'best-case',
        'worst-case',
        'what should i worry',
        'risk',
        'priorit',
        'close rate',
        'gap',
    ]
    if any(k in q for k in keyword_hits):
        return {'route': 'analytics_agent', 'reason': 'keyword heuristic'}
    raw = call_gemini(build_router_prompt(question))
    if not raw:
        return {'route': 'normal_intent', 'reason': 'router llm empty'}
    json_text = extract_json_object(raw) or raw.strip()
    try:
        obj = json.loads(json_text)
    except json.JSONDecodeError:
        return {'route': 'normal_intent', 'reason': 'router json parse failed'}
    route = str(obj.get('route', 'normal_intent')).strip().lower()
    if route not in {'normal_intent', 'analytics_agent'}:
        route = 'normal_intent'
    return {'route': route, 'reason': str(obj.get('reason', '')), '_raw': raw}


def apply_stage_bucket_to_intent(intent: dict, stage_bucket: str | None) -> dict:
    normalized_bucket = normalize_stage_bucket(stage_bucket)
    stage_rule = get_business_rules().get('stage_buckets', {}).get(normalized_bucket, {})
    mode = str(stage_rule.get('mode', 'none')).lower()
    values = [str(v) for v in stage_rule.get('values', [])]

    filters = intent.get('filters')
    if not isinstance(filters, list):
        filters = []
    preserved_filters = [
        f
        for f in filters
        if not (
            isinstance(f, dict)
            and str(f.get('field', '')).strip().lower() == 'deal_stage_name'
            and str(f.get('source', '')).strip().lower() == 'ui_stage_bucket'
        )
    ]

    if mode in {'in', 'not_in'} and values:
        preserved_filters.append(
            {
                'field': 'deal_stage_name',
                'operator': mode,
                'values': values,
                'source': 'ui_stage_bucket',
                'bucket': normalized_bucket,
            }
        )

    intent['filters'] = preserved_filters
    intent['stage_bucket'] = normalized_bucket
    return intent


def plan_intent(question: str, route: str = 'normal_intent', stage_bucket: str | None = None) -> dict:
    prompt = (
        build_intent_prompt_analytics(question, stage_bucket=normalize_stage_bucket(stage_bucket))
        if route == 'analytics_agent'
        else build_intent_prompt(question, stage_bucket=normalize_stage_bucket(stage_bucket))
    )
    raw = call_gemini(prompt)
    if not raw:
        raise RuntimeError('LLM returned no intent JSON.')
    json_text = extract_json_object(raw) or raw.strip()
    try:
        obj = json.loads(json_text)
    except json.JSONDecodeError:
        raise RuntimeError(f'Intent planner did not return valid JSON. Raw: {raw!r}')
    if not isinstance(obj, dict):
        raise RuntimeError('Intent planner JSON must be an object.')

    normalized = {
        'entity': obj.get('entity'),
        'metric': obj.get('metric'),
        'aggregation': obj.get('aggregation'),
        'time_period': obj.get('time_period'),
        'filters': obj.get('filters') if isinstance(obj.get('filters'), list) else [],
        'group_by': obj.get('group_by') if isinstance(obj.get('group_by'), list) else [],
        'order_by': obj.get('order_by'),
        'limit': obj.get('limit'),
        'threshold': obj.get('threshold'),
        'presentation': obj.get('presentation'),
    }
    if normalized['order_by'] is None and obj.get('sort') is not None:
        normalized['order_by'] = obj.get('sort')
    if normalized['aggregation'] is None and obj.get('agg') is not None:
        normalized['aggregation'] = obj.get('agg')
    if route == 'analytics_agent':
        normalized['comparison_type'] = obj.get('comparison_type')
        normalized['goal_type'] = obj.get('goal_type')
        normalized['analysis_mode'] = obj.get('analysis_mode')

    normalized['_raw'] = raw
    normalized['_route'] = route
    return apply_stage_bucket_to_intent(normalized, stage_bucket)
