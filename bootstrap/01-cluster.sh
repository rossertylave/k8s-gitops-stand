#!/usr/bin/env bash
# Створення локального реєстру образів і кластера k3d з декларативного опису.
source "$(dirname "$0")/lib.sh"
need docker k3d kubectl

if ! k3d registry list 2>/dev/null | grep -q "k3d-${REGISTRY_NAME}"; then
  log "Створення реєстру k3d-${REGISTRY_NAME}:${REGISTRY_PORT}"
  k3d registry create "${REGISTRY_NAME}" --port "${REGISTRY_PORT}"
fi

start=$(now_ms)
if ! k3d cluster list 2>/dev/null | grep -q "^${CLUSTER_NAME} "; then
  log "Створення кластера ${CLUSTER_NAME}"
  k3d cluster create --config "${ROOT}/cluster/k3d-config.yaml"
fi
kubectl wait --for=condition=Ready nodes --all --timeout=180s
end=$(now_ms)

echo "cluster_create_ms,$(( end - start ))" >> "${RESULTS}/bootstrap_times.csv"
kubectl get nodes -o wide
kubectl version -o json | python3 -c 'import json,sys; print("kubernetes (server):", json.load(sys.stdin)["serverVersion"]["gitVersion"])' \
  | tee -a "${RESULTS}/versions.txt"
