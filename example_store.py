import json
import sqlite3
from difflib import SequenceMatcher
from math import sqrt

from .config import EXAMPLES_DB_PATH
from .gemini_client import embed_text


def _connect():
    return sqlite3.connect(EXAMPLES_DB_PATH)


def init_examples_db() -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS sql_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            sql_text TEXT NOT NULL,
            tags TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        '''
    )
    cur.execute("PRAGMA table_info(sql_examples)")
    cols = {row[1] for row in cur.fetchall()}
    if 'embedding' not in cols:
        cur.execute('ALTER TABLE sql_examples ADD COLUMN embedding TEXT')
    conn.commit()
    conn.close()


def add_example(question: str, sql_text: str, tags=None, notes: str | None = None) -> int:
    init_examples_db()
    tags_json = json.dumps(tags or [])
    embedding_json = None
    try:
        embedding_json = json.dumps(embed_text(question.strip()))
    except Exception:
        embedding_json = None
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO sql_examples (question, sql_text, tags, notes, embedding) VALUES (?, ?, ?, ?, ?)',
        (question.strip(), sql_text.strip(), tags_json, (notes or '').strip(), embedding_json),
    )
    row_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return row_id


def list_examples(limit: int = 200) -> list[dict]:
    init_examples_db()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        '''
        SELECT id, question, sql_text, tags, notes, created_at, embedding
        FROM sql_examples
        ORDER BY id DESC
        LIMIT ?
        ''',
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    items = []
    for row in rows:
        tags = []
        try:
            tags = json.loads(row[3] or '[]')
        except Exception:
            tags = []
        items.append(
            {
                'id': row[0],
                'question': row[1],
                'sql_text': row[2],
                'tags': tags,
                'notes': row[4],
                'created_at': row[5],
                'embedding': row[6],
            }
        )
    return items


def delete_example(example_id: int) -> bool:
    init_examples_db()
    conn = _connect()
    cur = conn.cursor()
    cur.execute('DELETE FROM sql_examples WHERE id = ?', (int(example_id),))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def _token_set(text: str) -> set[str]:
    return {tok for tok in ''.join(c.lower() if c.isalnum() else ' ' for c in text).split() if len(tok) > 1}


def _score_similarity(a: str, b: str) -> float:
    a = (a or '').strip().lower()
    b = (b or '').strip().lower()
    if not a or not b:
        return 0.0
    seq = SequenceMatcher(None, a, b).ratio()
    ta = _token_set(a)
    tb = _token_set(b)
    jaccard = (len(ta & tb) / len(ta | tb)) if (ta and tb) else 0.0
    return (0.6 * seq) + (0.4 * jaccard)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sqrt(sum(x * x for x in a))
    nb = sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return -1.0
    return dot / (na * nb)


def find_similar_examples(question: str, top_k: int = 3, min_score: float = 0.35) -> list[dict]:
    candidates = list_examples(limit=500)
    scored: list[tuple[float, dict]] = []
    query_embedding = None
    try:
        query_embedding = embed_text(question)
    except Exception:
        query_embedding = None

    if query_embedding:
        for item in candidates:
            emb_raw = item.get('embedding')
            emb = None
            if emb_raw:
                try:
                    emb = json.loads(emb_raw)
                except Exception:
                    emb = None
            if not emb:
                try:
                    emb = embed_text(item['question'])
                    conn = _connect()
                    cur = conn.cursor()
                    cur.execute('UPDATE sql_examples SET embedding = ? WHERE id = ?', (json.dumps(emb), item['id']))
                    conn.commit()
                    conn.close()
                except Exception:
                    emb = None
            score = _cosine_similarity(query_embedding, emb) if emb else _score_similarity(question, item['question'])
            if score >= min_score:
                scored.append((score, item))
    else:
        for item in candidates:
            score = _score_similarity(question, item['question'])
            if score >= min_score:
                scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            'id': item['id'],
            'question': item['question'],
            'sql_text': item['sql_text'],
            'tags': item.get('tags', []),
            'notes': item.get('notes', ''),
            'score': round(score, 4),
        }
        for score, item in scored[:top_k]
    ]
