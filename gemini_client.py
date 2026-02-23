import json
import os
import threading
import time
from urllib import error, request

GEMINI_SEM = threading.Semaphore(1)


def gemini_request(payload: dict, *, timeout_s: int = 45, max_retries: int = 5) -> dict:
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY missing in .env')

    url = (
        'https://generativelanguage.googleapis.com/v1beta/models/'
        'gemini-2.0-flash:generateContent?key='
        + api_key
    )

    retryable_http = {429, 408, 500, 502, 503, 504}
    backoff_s = 1.5
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            body = json.dumps(payload).encode('utf-8')
            req = request.Request(url, data=body, headers={'Content-Type': 'application/json'})
            with GEMINI_SEM:
                with request.urlopen(req, timeout=timeout_s) as response:
                    return json.loads(response.read().decode('utf-8'))
        except error.HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')
            last_error = f'HTTP {exc.code}: {detail}'
            retry_after = exc.headers.get('Retry-After')
            if exc.code in retryable_http and attempt < max_retries:
                sleep_time = float(retry_after) if retry_after else backoff_s
                time.sleep(sleep_time)
                backoff_s = min(backoff_s * 2.0, 15.0)
                continue
            raise RuntimeError(last_error) from exc
        except error.URLError as exc:
            last_error = f'URLError: {exc}'
            if attempt < max_retries:
                time.sleep(backoff_s)
                backoff_s = min(backoff_s * 2.0, 15.0)
                continue
            raise RuntimeError(last_error) from exc

    raise RuntimeError(last_error or 'Gemini request failed.')


def call_gemini(prompt: str) -> str | None:
    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'temperature': 0.0},
    }
    data = gemini_request(payload, timeout_s=25, max_retries=2)
    candidates = data.get('candidates') or []
    if not candidates:
        return None
    parts = candidates[0].get('content', {}).get('parts') or []
    if not parts:
        return None
    return parts[0].get('text')


def embed_text(text: str) -> list[float]:
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY missing in .env')
    payload = {
        'model': 'models/text-embedding-004',
        'content': {'parts': [{'text': text}]},
    }
    body = json.dumps(payload).encode('utf-8')
    url = (
        'https://generativelanguage.googleapis.com/v1beta/models/'
        'text-embedding-004:embedContent?key='
        + api_key
    )
    req = request.Request(url, data=body, headers={'Content-Type': 'application/json'})
    data = None
    with GEMINI_SEM:
        with request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
    values = (data or {}).get('embedding', {}).get('values') or []
    if not values:
        raise RuntimeError('Embedding API returned no vector.')
    return [float(v) for v in values]
