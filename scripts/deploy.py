from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def load_versions() -> dict[str, str]:
    lines = (ROOT / "cluster" / "versions.env").read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines if "=" in line and not line.startswith("#"))


def run(*args: str) -> None:
    print(f"\n$ {' '.join(args)}", flush=True)
    subprocess.run(args, check=True)


def deploy_application() -> None:
    run("kubectl", "apply", "-k", str(ROOT / "kubernetes" / "base"))
    run("kubectl", "-n", "platform-demo", "rollout", "status",
        "deployment/demo-web", "--timeout=180s")


def deploy_gateway(version: str) -> None:
    run("helm", "upgrade", "--install", "eg",
        "oci://docker.io/envoyproxy/gateway-helm",
        "--version", version,
        "--namespace", "envoy-gateway-system", "--create-namespace",
        "--wait", "--timeout", "5m")
    run("kubectl", "wait", "--namespace", "envoy-gateway-system",
        "--for=condition=Available", "deployment/envoy-gateway", "--timeout=300s")
    run("kubectl", "apply", "-k", str(ROOT / "gateway"))
    run("kubectl", "-n", "platform-demo", "wait", "gateway/demo-gateway",
        "--for=condition=Programmed", "--timeout=180s")


def deploy_monitoring(docker_desktop: bool) -> None:
    command = [sys.executable, str(SCRIPTS / "deploy_monitoring.py")]
    if docker_desktop:
        command.append("--docker-desktop")
    run(*command)


def deploy_logging() -> None:
    run("kubectl", "-n", "logging", "delete", "job", "elasticsearch-setup",
        "--ignore-not-found")
    run("kubectl", "apply", "-k", str(ROOT / "logging"))
    run("kubectl", "-n", "logging", "rollout", "status",
        "statefulset/elasticsearch", "--timeout=300s")
    run("kubectl", "-n", "logging", "rollout", "status",
        "daemonset/fluentd", "--timeout=300s")
    run("kubectl", "-n", "logging", "wait", "job/elasticsearch-setup",
        "--for=condition=Complete", "--timeout=300s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy the whole demo platform.")
    parser.add_argument("--docker-desktop", action="store_true",
                        help="Use Docker Desktop specific settings.")
    args = parser.parse_args()

    run(sys.executable, str(SCRIPTS / "check_prerequisites.py"))
    versions = load_versions()

    deploy_application()
    deploy_gateway(versions["ENVOY_GATEWAY_VERSION"])
    deploy_monitoring(args.docker_desktop)
    deploy_logging()

    print("\nDeployment finished. Run: python scripts/verify.py")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode)