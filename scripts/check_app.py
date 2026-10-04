from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check that the demo web application is available."
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8080/",
        help="Application URL.",
    )
    parser.add_argument(
        "--expected",
        default="Hello World!",
        help="Expected response body without surrounding whitespace.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Request timeout in seconds.",
    )
    return parser.parse_args()


def check_application(url: str, expected: str, timeout: float) -> None:
    request = urllib.request.Request(
        url=url,
        method="GET",
        headers={
            "Accept": "text/plain",
            "User-Agent": "k8s-observability-smoke-test/1.0",
        },
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8").strip()
        status = response.status

    if status != 200:
        raise RuntimeError(f"unexpected HTTP status: {status}")

    if body != expected:
        raise RuntimeError(
            f"unexpected response body: expected {expected!r}, received {body!r}"
        )

    print(f"OK: {url} returned HTTP {status} and {body!r}")


def main() -> int:
    arguments = parse_arguments()

    try:
        check_application(
            url=arguments.url,
            expected=arguments.expected,
            timeout=arguments.timeout,
        )
    except (urllib.error.URLError, TimeoutError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
