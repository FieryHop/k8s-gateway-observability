from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from k8s_utils import port_forward

CHECKS = {
    "nginx targets up": 'count(up{job="demo-web"} == 1)',
    "nginx_up": "min(nginx_up)",
    "nginx requests counted": "sum(nginx_http_requests_total)",
    "envoy proxy live": "sum(envoy_server_live)",
}


@contextmanager
def port_forward(namespace: str, service: str, local: int, remote: int):
    process = subprocess.Popen(
        ["kubectl", "-n", namespace, "port-forward", "--address", "127.0.0.1",
         f"svc/{service}", f"{local}:{remote}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        yield
    finally:
        process.terminate()
        process.wait(timeout=10)


def query(base_url: str, expression: str) -> float | None:
    url = f"{base_url}/api/v1/query?{urllib.parse.urlencode({'query': expression})}"
    with urllib.request.urlopen(url, timeout=10) as response:
        payload = json.load(response)
    result = payload["data"]["result"]
    return float(result[0]["value"][1]) if result else None


def evaluate(base_url: str) -> dict[str, float | None]:
    return {name: query(base_url, expr) for name, expr in CHECKS.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Prometheus metrics.")
    parser.add_argument("--namespace", default="monitoring")
    parser.add_argument("--service", default="kps-prometheus")
    parser.add_argument("--port", type=int, default=19090)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    base_url = f"http://127.0.0.1:{args.port}"
    results: dict[str, float | None] = {}

    with port_forward(args.namespace, args.service, args.port, 9090):
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            try:
                results = evaluate(base_url)
            except (OSError, KeyError, ValueError):
                results = {}
            if results and all(value and value > 0 for value in results.values()):
                break
            time.sleep(5)

    failed = False
    for name in CHECKS:
        value = results.get(name)
        ok = bool(value and value > 0)
        failed |= not ok
        print(f"{'OK' if ok else 'FAIL'}: {name} = {value}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())