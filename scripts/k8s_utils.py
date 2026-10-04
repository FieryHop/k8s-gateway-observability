from __future__ import annotations

import socket
import subprocess
import time
from contextlib import contextmanager


def kubectl(*args: str) -> str:
    result = subprocess.run(
        ["kubectl", *args], capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def gateway_service(gateway: str = "demo-gateway") -> tuple[str, str]:
    output = kubectl(
        "get", "svc", "-A",
        "-l", f"gateway.envoyproxy.io/owning-gateway-name={gateway}",
        "-o", "jsonpath={.items[0].metadata.namespace}/{.items[0].metadata.name}",
    )
    namespace, _, name = output.partition("/")
    if not name:
        raise RuntimeError(f"Envoy service for gateway {gateway!r} not found")
    return namespace, name


def _wait_port(port: int, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as sock:
            sock.settimeout(1)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.5)
    raise TimeoutError(f"port-forward to 127.0.0.1:{port} did not become ready")


@contextmanager
def port_forward(namespace: str, service: str, local: int, remote: int):
    process = subprocess.Popen(
        ["kubectl", "-n", namespace, "port-forward", "--address", "127.0.0.1",
         f"svc/{service}", f"{local}:{remote}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        _wait_port(local, timeout=20)
        yield
    finally:
        process.terminate()
        process.wait(timeout=10)