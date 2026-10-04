from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from k8s_utils import gateway_service, port_forward

SCRIPTS = Path(__file__).resolve().parent
LOCAL_PORT = 18080


def run_script(name: str, *args: str) -> int:
    return subprocess.run([sys.executable, str(SCRIPTS / name), *args]).returncode


def main() -> int:
    namespace, service = gateway_service()
    print("== Application through Gateway API ==")
    with port_forward(namespace, service, LOCAL_PORT, 80):
        app_status = run_script("check_app.py", "--url", f"http://127.0.0.1:{LOCAL_PORT}/")

    print("== Prometheus ==")
    prometheus_status = run_script("check_prometheus.py")

    print("== Logging ==")
    logging_status = run_script("check_logging.py")

    statuses = {"application": app_status, "prometheus": prometheus_status,
                "logging": logging_status}
    print("\nSummary:")
    for name, status in statuses.items():
        print(f"  {'OK' if status == 0 else 'FAIL'}: {name}")
    return 1 if any(statuses.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())