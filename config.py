import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, '.env')
LOG_PATH = os.path.join(BASE_DIR, 'server_error.log')
SCHEMA_DETAILS_PATH = os.path.join(BASE_DIR, 'Schema_table_details.txt')
BUSINESS_RULES_PATH = os.path.join(BASE_DIR, 'business_rules.json')
EXAMPLES_DB_PATH = os.path.join(BASE_DIR, 'sql_examples.db')


def load_env(path: str = ENV_PATH) -> None:
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key, value)


def log_error(message: str) -> None:
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as handle:
            handle.write(message)
            if not message.endswith('\n'):
                handle.write('\n')
    except Exception:
        pass
