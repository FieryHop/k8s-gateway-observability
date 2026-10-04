from __future__ import annotations

import shutil
import subprocess
import sys

REQUIRED_TOOLS = ("kubectl", "helm")
MIN_PYTHON = (3, 11)


def main() -> int:
    errors: list[str] = []

    if sys.version_info < MIN_PYTHON:
        errors.append(f"Python {'.'.join(map(str, MIN_PYTHON))}+ is required")

    for tool in REQUIRED_TOOLS:
        if shutil.which(tool) is None:
            errors.append(f"{tool} not found in PATH")

    if not errors:
        result = subprocess.run(
            ["kubectl", "cluster-info"], capture_output=True, text=True
        )
        if result.returncode:
            errors.append("Kubernetes cluster is not reachable via kubectl")

    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())