from datetime import date, datetime
from decimal import Decimal


def format_rows(rows, columns):
    if not rows or not columns:
        return 'No results.'
    lines = [' | '.join(columns)]
    for row in rows[:25]:
        lines.append(' | '.join('' if v is None else str(v) for v in row))
    if len(rows) > 25:
        lines.append(f'... {len(rows) - 25} more rows')
    return '\n'.join(lines)


def json_value(value):
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def json_rows(rows):
    return [[json_value(cell) for cell in row] for row in rows]
