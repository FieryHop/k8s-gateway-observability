from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMESPACE = "monitoring"
RELEASE = "kps"
CHART = "oci://ghcr.io/prometheus-community/charts/kube-prometheus-stack"


def load_versions() -> dict[str, str]:
    lines = (ROOT / "cluster" / "versions.env").read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines if "=" in line and not line.startswith("#"))


def run(*args: str, stdin: str | None = None) -> str:
    result = subprocess.run(
        args, input=stdin, capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode:
        sys.exit(f"FAILED: {' '.join(args)}\n{result.stderr.strip()}")
    return result.stdout


def apply(manifest: dict) -> None:
    run("kubectl", "apply", "-f", "-", stdin=json.dumps(manifest))


def ensure_namespace() -> None:
    apply({"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": NAMESPACE}})


def ensure_grafana_secret() -> None:
    existing = run(
        "kubectl", "-n", NAMESPACE, "get", "secret", "grafana-admin",
        "-o", "name", "--ignore-not-found",
    )
    if existing.strip():
        print("Secret grafana-admin already exists, keeping it")
        return
    apply({
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "grafana-admin", "namespace": NAMESPACE},
        "type": "Opaque",
        "stringData": {
            "admin-user": "admin",
            "admin-password": secrets.token_urlsafe(24),
        },
    })
    print("Secret grafana-admin created")


def install_stack(version: str, extra_values: list[Path]) -> None:
    command = [
        "helm", "upgrade", "--install", RELEASE, CHART,
        "--version", version,
        "--namespace", NAMESPACE,
        "--values", str(ROOT / "monitoring" / "kube-prometheus-stack-values.yaml"),
    ]
    for values_file in extra_values:
        command += ["--values", str(values_file)]
    command += ["--wait", "--timeout", "10m"]
    subprocess.run(command, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy Prometheus stack and monitors.")
    parser.add_argument("--docker-desktop", action="store_true",
                        help="Apply Docker Desktop specific values.")
    args = parser.parse_args()

    versions = load_versions()
    extra = [ROOT / "monitoring" / "values-docker-desktop.yaml"] if args.docker_desktop else []

    ensure_namespace()
    ensure_grafana_secret()
    install_stack(versions["KUBE_PROMETHEUS_STACK_VERSION"], extra)
    subprocess.run(["kubectl", "apply", "-k", str(ROOT / "monitoring")], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())