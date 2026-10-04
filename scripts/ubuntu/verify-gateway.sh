#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-platform-demo}"
GATEWAY="${GATEWAY:-demo-gateway}"
LOCAL_PORT="${LOCAL_PORT:-18080}"
LOG_FILE="${LOG_FILE:-/tmp/gateway-port-forward.log}"

kubectl -n "${NAMESPACE}" wait "gateway/${GATEWAY}" \
  --for=condition=Programmed --timeout=180s

service="$(kubectl -n envoy-gateway-system get svc \
  -l "gateway.envoyproxy.io/owning-gateway-name=${GATEWAY}" \
  -l "gateway.envoyproxy.io/owning-gateway-namespace=${NAMESPACE}" \
  -o jsonpath='{.items[0].metadata.name}')"

if [[ -z "${service}" ]]; then
  echo "Envoy service for gateway ${GATEWAY} not found" >&2
  exit 1
fi

kubectl -n envoy-gateway-system port-forward --address 127.0.0.1 \
  "svc/${service}" "${LOCAL_PORT}:80" >"${LOG_FILE}" 2>&1 &
forward_pid=$!
trap 'kill "${forward_pid}" 2>/dev/null || true' EXIT

for _ in $(seq 1 30); do
  if curl -s -o /dev/null "http://127.0.0.1:${LOCAL_PORT}/"; then
    python3 scripts/verify_gateway.py --url "http://127.0.0.1:${LOCAL_PORT}"
    exit $?
  fi
  sleep 1
done

echo "Gateway is not reachable on port ${LOCAL_PORT}" >&2
cat "${LOG_FILE}" >&2
exit 1