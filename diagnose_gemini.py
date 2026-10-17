"""Manually diagnose the crawler's Gemini models without changing site data."""

import json
import os
import sys
import urllib.error
import urllib.request


MODELS = ('gemini-3.5-flash-lite', 'gemini-3.8-flash')


def probe(model, search, key):
    payload = {
        'contents': [{'parts': [{'text': (
            'Google検索を使って静岡県庁の公式サイトURLを1つ回答してください。'
            if search else '日本語で「接続成功」とだけ回答してください。'
        )}]}],
    }
    if search:
        payload['tools'] = [{'google_search': {}}]
    request = urllib.request.Request(
        f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'x-goog-api-key': key},
        method='POST',
    )
    label = f'{model} / ' + ('Google Search' if search else 'plain generation')
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.load(response)
        candidates = result.get('candidates', [])
        has_text = any(
            part.get('text') for candidate in candidates
            for part in candidate.get('content', {}).get('parts', [])
        )
        if not has_text:
            print(f'{label}: FAIL (HTTP 200 but no generated text)')
            return False
        grounded = any(c.get('groundingMetadata', {}).get('groundingChunks') for c in candidates)
        print(f'{label}: PASS (generated text; search sources present: {grounded})')
        return True
    except urllib.error.HTTPError as exc:
        print(f'{label}: FAIL HTTP {exc.code}')
        # Print API diagnostics, never request headers or the credential itself.
        body = exc.read().decode('utf-8', errors='replace')
        try:
            error = json.loads(body).get('error', {})
            diagnostic = {k: error[k] for k in ('status', 'message', 'details') if k in error}
            print(json.dumps(diagnostic, ensure_ascii=False).replace(key, '[REDACTED]'))
        except (ValueError, AttributeError, TypeError):
            print('Non-JSON error response; response body omitted.')
        return False
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f'{label}: FAIL ({type(exc).__name__}; connection or response error)')
        return False


def main():
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not key:
        print('FAIL: GEMINI_API_KEY is missing or empty in GitHub Actions Secrets.')
        return 1
    print('GEMINI_API_KEY: present (value hidden). Up to four API calls; no automatic retries.')
    results = [probe(model, search, key) for model in MODELS for search in (False, True)]
    print(f'Diagnostic requests passed: {sum(results)}/{len(results)}')
    print('429: inspect quotaMetric/quotaId/quotaValue and retryDelay above.')
    print('404: check model availability. 403: check project/API/key restrictions.')
    print('Plain PASS + Search FAIL: investigate search-specific availability or quota.')
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
