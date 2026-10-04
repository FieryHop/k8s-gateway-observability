from __future__ import annotations

import argparse
import sys
import urllib.request
from collections import Counter

STABLE = "Hello World!"
CANARY = "Hello from canary!"


def fetch(base: str, path: str = "/", headers: dict[str, str] | None = None) -> str:
    request = urllib.request.Request(base + path, headers=headers or {})
    with urllib.request.urlopen(request, timeout=5) as response:
        if response.status != 200:
            raise RuntimeError(f"{path}: HTTP {response.status}")
        return response.read().decode().strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify advanced Gateway API routing.")
    parser.add_argument("--url", default="http://127.0.0.1:18080")
    parser.add_argument("--requests", type=int, default=200)
    args = parser.parse_args()
    base = args.url.rstrip("/")

    checks = [
        ("default route", "/", {}, STABLE),
        ("path route /canary", "/canary", {}, CANARY),
        ("header route X-Canary", "/", {"X-Canary": "true"}, CANARY),
        ("host route canary.demo.local", "/", {"Host": "canary.demo.local"}, CANARY),
    ]
    failed = False
    for name, path, headers, expected in checks:
        try:
            actual = fetch(base, path, headers)
        except Exception as error:
            actual = f"error: {error}"
        ok = actual == expected
        failed |= not ok
        print(f"{'OK' if ok else 'FAIL'}: {name} -> {actual!r}")

    try:
        counts = Counter(fetch(base, "/split") for _ in range(args.requests))
    except Exception as error:
        print(f"FAIL: traffic split -> error: {error}")
        return 1
    share = counts[CANARY] / args.requests
    ok = 0.10 <= share <= 0.30
    failed |= not ok
    print(f"{'OK' if ok else 'FAIL'}: traffic split 80/20, canary share = {share:.0%} {dict(counts)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())