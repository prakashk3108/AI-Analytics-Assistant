import os
import time
import traceback

import pyodbc

from .config import SCHEMA_DETAILS_PATH, log_error

TABLE_ALLOWLIST = {'grp.FactSale'}
_SCHEMA_CACHE = {'text': None, 'at': 0.0}


def get_connection():
    server = os.environ.get('FABRIC_SQL_ENDPOINT')
    database = os.environ.get('FABRIC_DATABASE')
    tenant = os.environ.get('FABRIC_TENANT_ID')
    client_id = os.environ.get('FABRIC_CLIENT_ID')
    client_secret = os.environ.get('FABRIC_CLIENT_SECRET')
    if not server or not database:
        raise RuntimeError('FABRIC_SQL_ENDPOINT or FABRIC_DATABASE missing in .env')
    if not tenant or not client_id or not client_secret:
        raise RuntimeError('FABRIC_TENANT_ID/CLIENT_ID/CLIENT_SECRET missing in .env')
    conn_str = (
        'Driver={ODBC Driver 18 for SQL Server};'
        f'Server=tcp:{server},1433;'
        f'Database={database};'
        'Encrypt=yes;'
        'TrustServerCertificate=no;'
        'Authentication=ActiveDirectoryServicePrincipal;'
        f'UID={client_id};'
        f'PWD={client_secret};'
        f'Authority Id={tenant};'
    )
    return pyodbc.connect(conn_str)


def get_schema_text() -> str:
    now = time.time()
    if _SCHEMA_CACHE['text'] and now - _SCHEMA_CACHE['at'] < 300:
        return _SCHEMA_CACHE['text']
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''
            SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
            '''
        )
    except Exception:
        log_error(traceback.format_exc())
        conn.close()
        raise
    rows = cursor.fetchall()
    conn.close()
    tables: dict[str, list[str]] = {}
    for schema, table, column, dtype in rows:
        key = f'{schema}.{table}'
        if TABLE_ALLOWLIST and key not in TABLE_ALLOWLIST:
            continue
        tables.setdefault(key, []).append(f'{column} ({dtype})')
    lines = ['Database schema:']
    for table, cols in tables.items():
        lines.append(f'Table {table}: ' + ', '.join(cols))
    text = '\n'.join(lines)
    _SCHEMA_CACHE['text'] = text
    _SCHEMA_CACHE['at'] = now
    return text


def get_schema_details_text() -> str | None:
    if not os.path.exists(SCHEMA_DETAILS_PATH):
        return None
    with open(SCHEMA_DETAILS_PATH, 'r', encoding='utf-8') as handle:
        content = handle.read().strip()
    return content or None


def list_tables() -> list[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT TABLE_SCHEMA, TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_SCHEMA, TABLE_NAME
        '''
    )
    rows = cursor.fetchall()
    conn.close()
    tables = [f'{row[0]}.{row[1]}' for row in rows]
    if TABLE_ALLOWLIST:
        tables = [name for name in tables if name in TABLE_ALLOWLIST]
    return tables
