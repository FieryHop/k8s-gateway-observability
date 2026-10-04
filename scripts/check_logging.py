from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

from k8s_utils import gateway_service, port_forward


def get_json(url: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def find_record(es_url: str, marker: str) -> dict | None:
    query = {"size": 1, "query": {"match_phrase": {"uri": marker}}}
    try:
        hits = get_json(f"{es_url}/demo-web-*/_search", query)["hits"]["hits"]
    except urllib.error.HTTPError:
        return None
    return hits[0]["_source"] if hits else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify access logs reach Elasticsearch.")
    parser.add_argument("--app-port", type=int, default=18080)
    parser.add_argument("--es-port", type=int, default=19200)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()

    marker = uuid.uuid4().hex
    gw_namespace, gw_service = gateway_service()

    with port_forward(gw_namespace, gw_service, args.app_port, 80), \
         port_forward("logging", "elasticsearch", args.es_port, 9200):
        urllib.request.urlopen(
            f"http://127.0.0.1:{args.app_port}/?probe={marker}", timeout=10
        ).read()

        es_url = f"http://127.0.0.1:{args.es_port}"
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            record = find_record(es_url, marker)
            if record:
                print(
                    f"OK: pod={record.get('pod')} container={record.get('container')} "
                    f"status={record.get('status')} uri={record.get('uri')}"
                )
                return 0
            time.sleep(3)

    print("ERROR: record not found in Elasticsearch", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())