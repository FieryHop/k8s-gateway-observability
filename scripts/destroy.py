from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COMMANDS = [
    ["kubectl", "delete", "-k", str(ROOT / "logging"), "--ignore-not-found"],
    ["kubectl", "delete", "-k", str(ROOT / "monitoring"), "--ignore-not-found"],
    ["helm", "uninstall", "kps", "-n", "monitoring", "--ignore-not-found"],
    ["kubectl", "delete", "namespace", "monitoring", "--ignore-not-found"],
    ["kubectl", "delete", "-k", str(ROOT / "gateway"), "--ignore-not-found"],
    ["helm", "uninstall", "eg", "-n", "envoy-gateway-system", "--ignore-not-found"],
    ["kubectl", "delete", "-k", str(ROOT / "kubernetes" / "base"), "--ignore-not-found"],
]


def main() -> int:
    for command in COMMANDS:
        print(f"$ {' '.join(command)}", flush=True)
        subprocess.run(command, check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())