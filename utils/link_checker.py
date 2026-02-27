"""Check that all URLs in a Markdown document return HTTP 200."""

from __future__ import annotations

import re
import sys
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

URL_PATTERN = re.compile(r"https?://[^\s\)\]\"'>]+")
_TRAILING_PUNCT = re.compile(r"[.,;:!?]+$")
MAX_WORKERS = 10
TIMEOUT = 10


def extract_urls(text: str) -> list[str]:
    """Extract all HTTP(S) URLs from a text string."""
    raw = URL_PATTERN.findall(text)
    cleaned = [_TRAILING_PUNCT.sub("", u) for u in raw]
    return list(dict.fromkeys(cleaned))  # deduplicate, preserve order


def check_url(url: str) -> tuple[str, int | str]:
    """
    Check a single URL. Returns (url, status_code) or (url, error_message).
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ContentFactory/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return url, resp.status
    except urllib.error.HTTPError as e:
        return url, e.code
    except Exception as e:
        return url, str(e)


def check_file(path: Path) -> dict:
    """
    Check all URLs in a file.

    Returns:
      ok      — list of (url, status_code) that returned 2xx
      broken  — list of (url, error) that failed
      summary — human-readable summary string
    """
    if not path.exists():
        return {"ok": [], "broken": [], "summary": f"{path.name} not found"}

    text = path.read_text(encoding="utf-8")
    urls = extract_urls(text)

    if not urls:
        return {"ok": [], "broken": [], "summary": f"{path.name}: no URLs found"}

    ok, broken = [], []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_url, url): url for url in urls}
        for future in as_completed(futures):
            url, result = future.result()
            if isinstance(result, int) and 200 <= result < 300:
                ok.append((url, result))
            else:
                broken.append((url, result))

    lines = [f"Link check: {len(ok)}/{len(urls)} OK"]
    for url, err in broken:
        lines.append(f"  ✗ {err}: {url}")
    summary = "\n".join(lines)

    return {"ok": ok, "broken": broken, "summary": summary}


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        result = check_file(Path(arg))
        print(result["summary"])
        if result["broken"]:
            sys.exit(1)
