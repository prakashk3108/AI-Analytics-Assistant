import json
import os
import time
import traceback

from .config import BUSINESS_RULES_PATH, log_error

DEFAULT_BUSINESS_RULES = {
    'defaults': {
        'region': 'GBR',
        'reporting_currency': 'GBP',
        'stage_bucket': 'not_applied',
    },
    'allowed': {
        'regions': ['GBR', 'CAN'],
        'reporting_currencies': ['GBP', 'CAD'],
        'stage_buckets': ['not_applied', 'closed_won_forecast', 'forecast', 'bridge', 'upside', 'closed_won', 'pipeline'],
    },
    'mappings': {
        'region_to_country_code': {'GBR': 'GBR', 'CAN': 'CAN'},
        'region_to_currency_symbol': {'GBP': '£', 'CAD': 'C$'},
    },
    'constraints': {'legal_entity_name': 'HubSpot'},
    'stage_buckets': {
        'not_applied': {'mode': 'none', 'values': []},
        'closed_won': {'mode': 'in', 'values': ['Closed Won']},
        'closed_won_forecast': {'mode': 'in', 'values': ['Closed Won', 'Signing', 'In Finalization / Purchasing']},
        'forecast': {'mode': 'in', 'values': ['Signing', 'In Finalization / Purchasing']},
        'bridge': {'mode': 'in', 'values': ['In Negotiation', 'Proposal / Price Quote']},
        'upside': {'mode': 'in', 'values': ['Presales / Solution Architecture', 'Suspect Qualified']},
        'pipeline': {'mode': 'not_in', 'values': ['Closed Won', 'Closed Lost']},
    },
}

_CACHE = {'data': None, 'at': 0.0}


def get_business_rules() -> dict:
    now = time.time()
    if _CACHE['data'] and now - _CACHE['at'] < 10:
        return _CACHE['data']
    rules = DEFAULT_BUSINESS_RULES
    if os.path.exists(BUSINESS_RULES_PATH):
        try:
            with open(BUSINESS_RULES_PATH, 'r', encoding='utf-8') as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                rules = loaded
        except Exception:
            log_error(traceback.format_exc())
    _CACHE['data'] = rules
    _CACHE['at'] = now
    return rules


def normalize_region(region: str | None) -> str:
    rules = get_business_rules()
    defaults = rules.get('defaults', {})
    allowed = set(rules.get('allowed', {}).get('regions', []))
    code = (region or '').strip().upper()
    if code in allowed:
        return code
    return str(defaults.get('region', 'GBR')).upper()


def normalize_reporting_currency(code: str | None) -> str:
    rules = get_business_rules()
    defaults = rules.get('defaults', {})
    allowed = set(rules.get('allowed', {}).get('reporting_currencies', []))
    value = (code or '').strip().upper()
    if value in allowed:
        return value
    return str(defaults.get('reporting_currency', 'GBP')).upper()


def normalize_stage_bucket(stage_bucket: str | None) -> str:
    rules = get_business_rules()
    defaults = rules.get('defaults', {})
    allowed = set(rules.get('allowed', {}).get('stage_buckets', []))
    value = (stage_bucket or '').strip().lower().replace(' ', '_')
    if value in allowed:
        return value
    return str(defaults.get('stage_bucket', 'not_applied')).lower()


def country_code_for_region(region: str) -> str:
    mappings = get_business_rules().get('mappings', {}).get('region_to_country_code', {})
    return str(mappings.get(region, region)).upper()


def legal_entity_name() -> str:
    return str(get_business_rules().get('constraints', {}).get('legal_entity_name', 'HubSpot'))


def stage_bucket_rule_text(stage_bucket: str) -> str:
    rule = get_business_rules().get('stage_buckets', {}).get(stage_bucket, {})
    mode = str(rule.get('mode', 'in')).lower()
    values = [str(v) for v in rule.get('values', [])]
    if mode == 'none':
        return 'No stage bucket filter selected. Do not force a stage filter unless explicitly required by intent.'
    if not values:
        return 'No stage filter.'
    quoted = ', '.join(f"'{v}'" for v in values)
    if mode == 'not_in':
        return f'ds.deal_stage_name NOT IN ({quoted})'
    return f'ds.deal_stage_name IN ({quoted})'


def stage_bucket_predicate(stage_bucket: str, alias: str = 'ds') -> str:
    rule = get_business_rules().get('stage_buckets', {}).get(stage_bucket, {})
    mode = str(rule.get('mode', 'none')).lower()
    values = [str(v) for v in rule.get('values', [])]
    if mode == 'none' or not values:
        return '1=1'
    quoted = ', '.join(f"'{v}'" for v in values)
    col = f'{alias}.deal_stage_name'
    if mode == 'not_in':
        return f'{col} NOT IN ({quoted})'
    return f'{col} IN ({quoted})'
