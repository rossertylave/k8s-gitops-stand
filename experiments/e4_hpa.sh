#!/usr/bin/env bash
# E4. Автомасштабування під змінним навантаженням.
# Той самий профіль навантаження (k6/ramp.js) подається на:
#   dev    - HPA catalog: 2..6 реплік;
#   manual - фіксовані 2 репліки (min = max = 2).
# Використання: e4_hpa.sh <dev|manual>
# Результат: results/e4_<env>_hpa.csv      (t_s,current,desired,ready,cpu_util_pct)
#            results/e4_<env>_k6.csv.gz     (сирі дані k6)
#            results/e4_<env>_summary.json  (підсумок k6)
source "$(dirname "$0")/../bootstrap/lib.sh"
need kubectl k6

env_name="${1:?dev | manual}"
ns="shop-${env_name}"
csv="${RESULTS}/e4_${env_name}_hpa.csv"
echo "t_s,current,desired,ready,cpu_util_pct" > "${csv}"

sampler() {
  local start; start=$(date +%s)
  while true; do
    local line ready
    line="$(kubectl -n "${ns}" get hpa catalog \
      -o jsonpath='{.status.currentReplicas},{.status.desiredReplicas},{.status.currentMetrics[0].resource.current.averageUtilization}' 2>/dev/null || echo ',,')"
    ready="$(kubectl -n "${ns}" get deployment catalog -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo '')"
    IFS=',' read -r current desired util <<< "${line}"
    echo "$(( $(date +%s) - start )),${current},${desired},${ready},${util}" >> "${csv}"
    sleep 5
  done
}

sampler &
sampler_pid=$!
trap 'kill "${sampler_pid}" 2>/dev/null || true' EXIT

RATE_LOW="${RATE_LOW:-5}" RATE_HIGH="${RATE_HIGH:-30}" WORK="${WORK:-1}" \
HOST_HEADER="${ns}.localhost" BASE_URL="${BASE_URL}" \
  k6 run --quiet \
    --summary-export "${RESULTS}/e4_${env_name}_summary.json" \
    --out "csv=${RESULTS}/e4_${env_name}_k6.csv.gz" \
    "${ROOT}/experiments/k6/ramp.js"

log "Готово: ${csv}"
